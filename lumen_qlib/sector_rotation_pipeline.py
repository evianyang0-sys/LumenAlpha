#!/usr/bin/env python3
"""Build a first-principles sector-rotation signal layer and dashboard data.

The pipeline deliberately keeps upstream projects separate:

- qlib contributes factor-style, cross-sectional signals.
- LumenAlpha contributes explainable technical signals.
- Eastmoney contributes current popularity rank.
- The local tech taxonomy contributes sector membership and hierarchy.

All signals are normalized into one long table with source labels.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import akshare as ak
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
LUMEN_PATH = ROOT / "LumenAlpha" / "stock_analyzer_project"
if str(LUMEN_PATH) not in sys.path:
    sys.path.insert(0, str(LUMEN_PATH))

try:
    from indicators import generate_analysis  # type: ignore
except Exception:  # noqa: BLE001
    generate_analysis = None

try:
    from advanced_signals import AdvancedSignalGenerator  # type: ignore
except Exception:  # noqa: BLE001
    AdvancedSignalGenerator = None


DEFAULT_DETAIL = ROOT / "data/a_share_hot_rank/a_share_hot_rank_top2000_tech_reclassified_latest.csv"
DEFAULT_BOARD_SUMMARY = ROOT / "data/a_share_hot_rank/a_share_hot_rank_top2000_by_designed_board_latest.csv"
DEFAULT_OUTPUT = ROOT / "data/sector_rotation"
DEFAULT_WEB_DATA = ROOT / "web/sector_rotation_dashboard/dashboard_data.js"


TECH_BOARD_ORDER = [
    "科技>AI算力与数据中心>算力服务器",
    "科技>AI算力与数据中心>算力基础设施",
    "科技>AI算力与数据中心>液冷温控",
    "科技>光通信与高速互联>光模块/CPO",
    "科技>光通信与高速互联>铜缆高速连接",
    "科技>PCB与电子制造>PCB",
    "科技>半导体与先进封装>芯片/半导体",
    "科技>半导体与先进封装>先进封装",
    "科技>半导体与先进封装>半导体设备材料",
    "科技>软件AI与信创>AI应用",
    "科技>软件AI与信创>信创与数据要素",
    "科技>AI终端与消费电子>AI终端",
    "科技>机器人与智能汽车>机器人",
    "科技>机器人与智能汽车>智能汽车",
]

ANCHOR_NAMES = [
    "工业富联",
    "胜宏科技",
    "天孚通信",
    "英维克",
    "中际旭创",
    "新易盛",
    "沪电股份",
    "深南电路",
    "浪潮信息",
    "寒武纪",
]

PROXY_ENV_KEYS = [
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build sector rotation unified signals and dashboard data.")
    parser.add_argument("--detail", default=str(DEFAULT_DETAIL), help="Tech-reclassified hot-rank detail CSV.")
    parser.add_argument("--board-summary", default=str(DEFAULT_BOARD_SUMMARY), help="Designed board summary CSV.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT), help="Output directory.")
    parser.add_argument("--web-data", default=str(DEFAULT_WEB_DATA), help="Generated dashboard_data.js path.")
    parser.add_argument("--history-days", type=int, default=180, help="Calendar days of stock history to fetch.")
    parser.add_argument("--curve-days", type=int, default=60, help="Trading days to keep for sector curves.")
    parser.add_argument("--chart-days", type=int, default=30, help="Trading days to keep for stock and sector k-line charts.")
    parser.add_argument("--marker-days", type=int, default=5, help="Recent trading days to mark significant signals on k-line charts.")
    parser.add_argument("--top-boards", type=int, default=20, help="Boards to visualize.")
    parser.add_argument("--leaders-per-board", type=int, default=8, help="Leaders sampled per board.")
    parser.add_argument("--max-stocks", type=int, default=180, help="Max unique stocks to fetch.")
    parser.add_argument("--workers", type=int, default=6, help="History fetch workers.")
    parser.add_argument("--refresh-history", action="store_true", help="Ignore cached history files.")
    parser.add_argument("--keep-proxy", action="store_true", help="Keep proxy environment variables for market data requests.")
    return parser.parse_args()


def clear_proxy_env() -> None:
    for key in PROXY_ENV_KEYS:
        os.environ.pop(key, None)


def normalize_code(value: Any) -> str:
    text = str(value).strip()
    digits = "".join(ch for ch in text if ch.isdigit())
    return digits[-6:].zfill(6) if digits else ""


def clean_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def read_inputs(detail_path: Path, summary_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    detail = pd.read_csv(detail_path, dtype={"code": str})
    detail["code"] = detail["code"].map(normalize_code)
    detail["rank"] = pd.to_numeric(detail["rank"], errors="coerce")
    detail = detail.dropna(subset=["rank"]).copy()
    detail["rank"] = detail["rank"].astype(int)
    detail["board_path"] = detail["board_path"].map(clean_str)
    detail["board_l1"] = detail["board_l1"].map(clean_str)
    detail["board_l2"] = detail["board_l2"].map(clean_str)
    detail["board_l3"] = detail["board_l3"].map(clean_str)
    detail["is_tech"] = detail["is_tech"].astype(bool)

    summary = pd.read_csv(summary_path)
    summary["board_path"] = summary["board_path"].map(clean_str)
    summary["is_tech"] = summary["is_tech"].astype(bool)
    return detail, summary


def select_boards(summary: pd.DataFrame, top_boards: int) -> list[str]:
    board_paths: list[str] = []
    available = set(summary["board_path"])
    for board in TECH_BOARD_ORDER:
        if board in available:
            board_paths.append(board)

    tech_extra = (
        summary[summary["is_tech"]]
        .sort_values(["stock_count", "best_rank"], ascending=[False, True])["board_path"]
        .tolist()
    )
    for board in tech_extra:
        if board not in board_paths:
            board_paths.append(board)

    non_tech = (
        summary[~summary["is_tech"]]
        .sort_values(["stock_count", "best_rank"], ascending=[False, True])["board_path"]
        .head(max(4, top_boards // 4))
        .tolist()
    )
    for board in non_tech:
        if board not in board_paths:
            board_paths.append(board)

    return board_paths[:top_boards]


def select_stocks(
    detail: pd.DataFrame,
    boards: list[str],
    leaders_per_board: int,
    max_stocks: int,
) -> pd.DataFrame:
    frames = []
    for board_order, board in enumerate(boards):
        frame = (
            detail[detail["board_path"] == board]
            .sort_values("rank")
            .head(leaders_per_board)
        )
        frame = frame.assign(_pick_priority=0, _board_order=board_order)
        frames.append(frame)

    frames.append(detail[detail["name"].isin(ANCHOR_NAMES)].assign(_pick_priority=1, _board_order=999))
    frames.append(detail[detail["is_tech"]].sort_values("rank").head(50).assign(_pick_priority=2, _board_order=999))
    selected = (
        pd.concat(frames, ignore_index=True)
        .sort_values(["_pick_priority", "_board_order", "rank"], ascending=[True, True, True])
        .drop_duplicates("code")
        .head(max_stocks)
        .drop(columns=["_pick_priority", "_board_order"], errors="ignore")
    )
    return selected.reset_index(drop=True)


def parse_history_cache(df: pd.DataFrame, code: str) -> pd.DataFrame:
    if df is None or df.empty or "日期" not in df.columns:
        return pd.DataFrame()
    frame = df.copy()
    frame["日期"] = pd.to_datetime(frame["日期"], errors="coerce")
    for col in [c for c in frame.columns if c != "日期" and c != "代码"]:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    frame["代码"] = code
    return frame.dropna(subset=["日期", "收盘"]).sort_values("日期").drop_duplicates("日期", keep="last").reset_index(drop=True)


def read_history_cache(path: Path, code: str) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return parse_history_cache(pd.read_csv(path), code)
    except Exception:
        return pd.DataFrame()


def load_cached_history(code: str, cache_dir: Path) -> tuple[pd.DataFrame, str]:
    stable_path = cache_dir / f"{code}.csv"
    cached = read_history_cache(stable_path, code)
    if not cached.empty:
        return cached, "cache"

    legacy_paths = sorted(cache_dir.glob(f"{code}_*.csv"), key=lambda path: path.stat().st_mtime, reverse=True)
    for path in legacy_paths:
        cached = read_history_cache(path, code)
        if not cached.empty:
            cached.to_csv(stable_path, index=False, encoding="utf-8-sig")
            return cached, "cache_legacy"
    return pd.DataFrame(), ""


def trim_history_window(df: pd.DataFrame, start_date: str) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    start_ts = pd.to_datetime(start_date)
    return df[df["日期"] >= start_ts].sort_values("日期").reset_index(drop=True)


def sina_symbol(code: str) -> str:
    if code.startswith(("6", "9")):
        return f"sh{code}"
    if code.startswith(("4", "8")):
        return f"bj{code}"
    return f"sz{code}"


def fetch_history_from_akshare(code: str, start_date: str, end_date: str) -> pd.DataFrame:
    last_error = ""
    try:
        df = ak.stock_zh_a_hist(
            symbol=code,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust="qfq",
        )
        if df is not None and not df.empty:
            keep = ["日期", "开盘", "收盘", "最高", "最低", "成交量", "成交额", "涨跌幅", "换手率"]
            existing = [col for col in keep if col in df.columns]
            parsed = parse_history_cache(df[existing].copy(), code)
            parsed.attrs["history_source"] = "eastmoney"
            return parsed
    except Exception as exc:  # noqa: BLE001
        last_error = f"eastmoney {type(exc).__name__}: {exc}"

    try:
        df = ak.stock_zh_a_daily(
            symbol=sina_symbol(code),
            start_date=start_date,
            end_date=end_date,
            adjust="qfq",
        )
    except Exception as exc:  # noqa: BLE001
        sina_error = f"sina {type(exc).__name__}: {exc}"
        raise RuntimeError("; ".join(item for item in [last_error, sina_error] if item)) from exc

    if df is None or df.empty:
        return pd.DataFrame()
    df = df.rename(
        columns={
            "date": "日期",
            "open": "开盘",
            "close": "收盘",
            "high": "最高",
            "low": "最低",
            "volume": "成交量",
            "amount": "成交额",
            "turnover": "换手率",
        }
    )
    keep = ["日期", "开盘", "收盘", "最高", "最低", "成交量", "成交额", "换手率"]
    existing = [col for col in keep if col in df.columns]
    parsed = parse_history_cache(df[existing].copy(), code)
    if not parsed.empty:
        parsed["涨跌幅"] = parsed["收盘"].pct_change() * 100
        parsed.attrs["history_source"] = "sina"
    return parsed


def fetch_history_one(code: str, start_date: str, end_date: str, cache_dir: Path, refresh: bool) -> tuple[str, pd.DataFrame, str]:
    stable_cache_path = cache_dir / f"{code}.csv"
    requested_start_date = start_date
    fetch_start_date = start_date
    cached = pd.DataFrame()
    cache_status = ""
    if not refresh:
        cached, cache_status = load_cached_history(code, cache_dir)
        if not cached.empty:
            last_cached = pd.to_datetime(cached["日期"]).max()
            end_ts = pd.to_datetime(end_date)
            if pd.notna(last_cached) and last_cached >= end_ts:
                return code, trim_history_window(cached, requested_start_date), cache_status
            if pd.notna(last_cached):
                fetch_start_date = (last_cached + timedelta(days=1)).strftime("%Y%m%d")

    last_error = ""
    for attempt in range(3):
        try:
            df = fetch_history_from_akshare(code, fetch_start_date, end_date)
            if df.empty:
                if not cached.empty:
                    return code, trim_history_window(cached, requested_start_date), f"{cache_status}_no_new_rows"
                return code, pd.DataFrame(), "empty"
            history_source = str(df.attrs.get("history_source") or "akshare")
            if not cached.empty:
                df = (
                    pd.concat([cached, df], ignore_index=True)
                    .sort_values("日期")
                    .drop_duplicates("日期", keep="last")
                    .reset_index(drop=True)
                )
            df.to_csv(stable_cache_path, index=False, encoding="utf-8-sig")
            time.sleep(0.05)
            return code, trim_history_window(df, requested_start_date), f"{history_source}_incremental" if cache_status else history_source
        except Exception as exc:  # noqa: BLE001
            last_error = f"{type(exc).__name__}: {exc}"
            time.sleep(0.4 * (attempt + 1))
    if not cached.empty:
        return code, trim_history_window(cached, requested_start_date), f"stale_{cache_status}: {last_error}"
    return code, pd.DataFrame(), f"error: {last_error}"


def fetch_histories(stocks: pd.DataFrame, output_dir: Path, history_days: int, workers: int, refresh: bool) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    cache_dir = output_dir / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=history_days)).strftime("%Y%m%d")
    histories: dict[str, pd.DataFrame] = {}
    rows = []
    codes = stocks["code"].drop_duplicates().tolist()
    print(f"Fetching history for {len(codes)} stocks...")
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = [
            executor.submit(fetch_history_one, code, start_date, end_date, cache_dir, refresh)
            for code in codes
        ]
        for idx, future in enumerate(as_completed(futures), start=1):
            code, df, status = future.result()
            histories[code] = df
            rows.append({"code": code, "rows": int(len(df)), "status": status})
            if idx % 20 == 0 or idx == len(codes):
                print(f"  history {idx}/{len(codes)}")
    return histories, pd.DataFrame(rows)


def pct_rank(series: pd.Series, higher_is_better: bool = True) -> pd.Series:
    ranked = series.rank(pct=True, ascending=higher_is_better)
    return ranked.fillna(0.5) * 100


@dataclass
class StockFeature:
    code: str
    close: float | None = None
    ret_1d: float | None = None
    ret_5d: float | None = None
    ret_20d: float | None = None
    ma20_bias: float | None = None
    volume_ratio_20: float | None = None
    volatility_20: float | None = None


def compute_price_features(histories: dict[str, pd.DataFrame]) -> pd.DataFrame:
    features = []
    for code, df in histories.items():
        if df is None or len(df) < 25:
            features.append(StockFeature(code).__dict__)
            continue
        close = df["收盘"].astype(float)
        volume = df["成交量"].astype(float)
        ret = close.pct_change()
        ma20 = close.rolling(20).mean()
        vol20 = volume.rolling(20).mean()
        features.append(
            StockFeature(
                code=code,
                close=float(close.iloc[-1]),
                ret_1d=float(close.iloc[-1] / close.iloc[-2] - 1) if len(close) >= 2 else None,
                ret_5d=float(close.iloc[-1] / close.iloc[-6] - 1) if len(close) >= 6 else None,
                ret_20d=float(close.iloc[-1] / close.iloc[-21] - 1) if len(close) >= 21 else None,
                ma20_bias=float(close.iloc[-1] / ma20.iloc[-1] - 1) if pd.notna(ma20.iloc[-1]) else None,
                volume_ratio_20=float(volume.iloc[-1] / vol20.iloc[-1]) if pd.notna(vol20.iloc[-1]) and vol20.iloc[-1] else None,
                volatility_20=float(ret.rolling(20).std().iloc[-1]) if pd.notna(ret.rolling(20).std().iloc[-1]) else None,
            ).__dict__
        )
    feature_df = pd.DataFrame(features)
    for col in ["ret_1d", "ret_5d", "ret_20d", "ma20_bias", "volume_ratio_20", "volatility_20"]:
        feature_df[col] = pd.to_numeric(feature_df[col], errors="coerce")

    feature_df["qlib_mom_5_rank"] = pct_rank(feature_df["ret_5d"], True)
    feature_df["qlib_mom_20_rank"] = pct_rank(feature_df["ret_20d"], True)
    feature_df["qlib_ma20_bias_rank"] = pct_rank(feature_df["ma20_bias"], True)
    feature_df["qlib_volume_rank"] = pct_rank(feature_df["volume_ratio_20"], True)
    feature_df["qlib_volatility_rank"] = pct_rank(feature_df["volatility_20"], False)
    feature_df["qlib_factor_score"] = (
        0.30 * feature_df["qlib_mom_5_rank"]
        + 0.30 * feature_df["qlib_mom_20_rank"]
        + 0.20 * feature_df["qlib_ma20_bias_rank"]
        + 0.15 * feature_df["qlib_volume_rank"]
        + 0.05 * feature_df["qlib_volatility_rank"]
    ).round(2)
    return feature_df


def signal_row(
    stock: pd.Series,
    source_project: str,
    source_module: str,
    signal_name: str,
    signal_value: Any,
    signal_score: float,
    direction: str,
    evidence: str,
    horizon: str = "daily",
) -> dict[str, Any]:
    return {
        "date": datetime.now().date().isoformat(),
        "code": stock["code"],
        "name": stock["name"],
        "board_path": stock.get("board_path", ""),
        "board_l1": stock.get("board_l1", ""),
        "board_l2": stock.get("board_l2", ""),
        "board_l3": stock.get("board_l3", ""),
        "source_project": source_project,
        "source_module": source_module,
        "signal_name": signal_name,
        "signal_value": signal_value,
        "signal_score": round(float(signal_score), 4),
        "direction": direction,
        "horizon": horizon,
        "evidence": evidence,
    }


def build_qlib_signal_rows(selected: pd.DataFrame, feature_df: pd.DataFrame) -> list[dict[str, Any]]:
    merged = selected.merge(feature_df, on="code", how="left")
    rows: list[dict[str, Any]] = []
    for _, stock in merged.iterrows():
        rows.append(signal_row(stock, "qlib", "alpha_formula_adapter", "qlib_factor_score", stock.get("qlib_factor_score"), stock.get("qlib_factor_score", 0), "bullish", "0.30*mom5 + 0.30*mom20 + 0.20*MA20_bias + 0.15*volume + 0.05*low_vol"))
        rows.append(signal_row(stock, "qlib", "alpha_formula_adapter", "momentum_20d", stock.get("ret_20d"), (stock.get("qlib_mom_20_rank") or 0) - 50, "bullish" if (stock.get("ret_20d") or 0) >= 0 else "bearish", "close / Ref(close, 20) - 1"))
        rows.append(signal_row(stock, "qlib", "alpha_formula_adapter", "volume_ratio_20d", stock.get("volume_ratio_20"), (stock.get("qlib_volume_rank") or 0) - 50, "bullish" if (stock.get("volume_ratio_20") or 0) >= 1 else "neutral", "volume / Mean(volume, 20)"))
    return rows


def to_lumen_frame(df: pd.DataFrame) -> pd.DataFrame:
    frame = df.copy()
    required = ["日期", "开盘", "收盘", "最高", "最低", "成交量"]
    return frame[[col for col in required if col in frame.columns]].copy()


def build_lumen_signal_rows(selected: pd.DataFrame, histories: dict[str, pd.DataFrame]) -> tuple[list[dict[str, Any]], pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    summary_rows = []
    for _, stock in selected.iterrows():
        code = stock["code"]
        df = histories.get(code, pd.DataFrame())
        if df is None or len(df) < 60 or generate_analysis is None:
            summary_rows.append({"code": code, "lumen_score": np.nan, "lumen_rating": "no_data", "lumen_signal_count": 0})
            continue
        try:
            analysis = generate_analysis(to_lumen_frame(df))
            lumen_score = float(analysis.get("score", 0) or 0)
            rating = clean_str(analysis.get("rating", ""))
            signals = analysis.get("signals", []) or []
            rows.append(signal_row(stock, "LumenAlpha", "SignalGenerator", "lumen_total_score", lumen_score, max(-100, min(100, lumen_score * 16)), "bullish" if lumen_score > 0 else "bearish" if lumen_score < 0 else "neutral", f"rating={rating}; signal_count={len(signals)}"))
            for signal in sorted(signals, key=lambda item: abs(float(item.get("score", 0) or 0)), reverse=True)[:6]:
                sig_score = float(signal.get("score", 0) or 0)
                direction = signal.get("type") or ("bullish" if sig_score > 0 else "bearish" if sig_score < 0 else "neutral")
                rows.append(signal_row(stock, "LumenAlpha", "SignalGenerator", signal.get("name", "signal"), sig_score, sig_score * 20, direction, clean_str(signal.get("description", "")), clean_str(signal.get("category", "technical"))))

            if AdvancedSignalGenerator is not None:
                adv = AdvancedSignalGenerator(to_lumen_frame(df)).calculate_all_advanced_indicators()
                adv_signals = AdvancedSignalGenerator(adv).generate_advanced_signals()
                for name, score, direction_cn, desc in adv_signals[:5]:
                    direction = "bullish" if direction_cn == "看多" else "bearish" if direction_cn == "看空" else "neutral"
                    rows.append(signal_row(stock, "LumenAlpha", "AdvancedSignalGenerator", name, score, float(score) * 20, direction, desc, "pattern"))

            summary_rows.append({"code": code, "lumen_score": lumen_score, "lumen_rating": rating, "lumen_signal_count": len(signals)})
        except Exception as exc:  # noqa: BLE001
            summary_rows.append({"code": code, "lumen_score": np.nan, "lumen_rating": f"error: {type(exc).__name__}", "lumen_signal_count": 0})
    return rows, pd.DataFrame(summary_rows)


def build_popularity_signal_rows(selected: pd.DataFrame) -> list[dict[str, Any]]:
    rows = []
    for _, stock in selected.iterrows():
        rank = float(stock.get("rank", np.nan))
        market_all = float(stock.get("market_all_count", 5528) or 5528)
        pop_score = 100 * (1 - (rank - 1) / max(market_all, 1)) if pd.notna(rank) else 0
        rows.append(signal_row(stock, "Eastmoney", "stockrank", "hot_rank_score", rank, pop_score, "bullish", f"rank={int(rank) if pd.notna(rank) else ''}/{int(market_all)}", "intraday"))
        if "rank_change" in stock:
            change = float(stock.get("rank_change", 0) or 0)
            rows.append(signal_row(stock, "Eastmoney", "stockrank", "rank_change", change, max(-50, min(50, change)), "bullish" if change > 0 else "neutral", "positive means popularity rank improved in source feed", "intraday"))
    return rows


def build_sector_curves(
    detail: pd.DataFrame,
    boards: list[str],
    histories: dict[str, pd.DataFrame],
    curve_days: int,
    leaders_per_board: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    curve_rows = []
    board_rows = []
    for board in boards:
        members = detail[detail["board_path"] == board].sort_values("rank").head(leaders_per_board)
        series_parts = []
        used = []
        for _, stock in members.iterrows():
            df = histories.get(stock["code"], pd.DataFrame())
            if df is None or len(df) < 25:
                continue
            s = df[["日期", "收盘"]].tail(curve_days + 20).copy()
            s = s.dropna()
            if s.empty:
                continue
            s["value"] = s["收盘"] / s["收盘"].iloc[0] * 100
            s = s[["日期", "value"]].rename(columns={"value": stock["code"]})
            series_parts.append(s)
            used.append(f"{stock['code']}:{stock['name']}")
        if not series_parts:
            continue
        merged = series_parts[0]
        for part in series_parts[1:]:
            merged = merged.merge(part, on="日期", how="outer")
        merged = merged.sort_values("日期").tail(curve_days)
        value_cols = [col for col in merged.columns if col != "日期"]
        merged["sector_index"] = merged[value_cols].mean(axis=1)
        first = merged["sector_index"].dropna().iloc[0] if merged["sector_index"].notna().any() else 100
        merged["sector_index"] = merged["sector_index"] / first * 100
        merged["date"] = pd.to_datetime(merged["日期"]).dt.strftime("%Y-%m-%d")
        for _, row in merged.iterrows():
            curve_rows.append({"board_path": board, "date": row["date"], "sector_index": round(float(row["sector_index"]), 3)})
        last = merged["sector_index"].dropna()
        ret_5 = last.iloc[-1] / last.iloc[-6] - 1 if len(last) >= 6 else np.nan
        ret_20 = last.iloc[-1] / last.iloc[-21] - 1 if len(last) >= 21 else np.nan
        board_rows.append(
            {
                "board_path": board,
                "curve_member_count": len(used),
                "curve_members": " | ".join(used[:8]),
                "sector_ret_5d": ret_5,
                "sector_ret_20d": ret_20,
            }
        )
    return pd.DataFrame(curve_rows), pd.DataFrame(board_rows)


def aggregate_leader_cards(
    selected: pd.DataFrame,
    feature_df: pd.DataFrame,
    lumen_summary: pd.DataFrame,
    signal_df: pd.DataFrame,
    board_curve_summary: pd.DataFrame,
) -> pd.DataFrame:
    leaders = selected.merge(feature_df, on="code", how="left").merge(lumen_summary, on="code", how="left")
    board_strength = board_curve_summary[["board_path", "sector_ret_5d", "sector_ret_20d"]].copy()
    board_strength["sector_trend_score"] = (
        pct_rank(board_strength["sector_ret_5d"], True) * 0.45
        + pct_rank(board_strength["sector_ret_20d"], True) * 0.55
    )
    leaders = leaders.merge(board_strength[["board_path", "sector_ret_5d", "sector_ret_20d", "sector_trend_score"]], on="board_path", how="left")
    market_all = pd.to_numeric(leaders.get("market_all_count", pd.Series([5528] * len(leaders))), errors="coerce").fillna(5528)
    leaders["popularity_score"] = 100 * (1 - (leaders["rank"] - 1) / market_all.clip(lower=1))
    leaders["lumen_score_norm"] = pct_rank(pd.to_numeric(leaders["lumen_score"], errors="coerce"), True)
    leaders["sector_trend_score"] = leaders["sector_trend_score"].fillna(50)
    leaders["combined_score"] = (
        0.35 * leaders["popularity_score"].fillna(0)
        + 0.30 * leaders["qlib_factor_score"].fillna(50)
        + 0.22 * leaders["lumen_score_norm"].fillna(50)
        + 0.13 * leaders["sector_trend_score"].fillna(50)
    ).round(2)

    top_signals = []
    for code, g in signal_df.sort_values("signal_score", ascending=False).groupby("code"):
        snippets = []
        for _, sig in g.head(5).iterrows():
            snippets.append(f"{sig['source_project']}:{sig['signal_name']}({sig['signal_score']:.1f})")
        top_signals.append({"code": code, "top_signals": " | ".join(snippets)})
    leaders = leaders.merge(pd.DataFrame(top_signals), on="code", how="left")
    return leaders.sort_values(["combined_score", "rank"], ascending=[False, True]).reset_index(drop=True)


def records_for_json(df: pd.DataFrame) -> list[dict[str, Any]]:
    clean = df.replace({np.nan: None})
    records = clean.to_dict("records")
    return records


def json_float(value: Any, digits: int = 4) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def history_to_candles(df: pd.DataFrame, days: int) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []
    need = ["日期", "开盘", "最高", "最低", "收盘"]
    if any(col not in df.columns for col in need):
        return []
    frame = df.sort_values("日期").tail(days).copy()
    candles = []
    for _, row in frame.iterrows():
        candles.append(
            {
                "date": pd.to_datetime(row["日期"]).strftime("%Y-%m-%d"),
                "open": json_float(row.get("开盘")),
                "high": json_float(row.get("最高")),
                "low": json_float(row.get("最低")),
                "close": json_float(row.get("收盘")),
                "volume": json_float(row.get("成交量"), 2),
                "pct": json_float(row.get("涨跌幅"), 2),
            }
        )
    return candles


def add_marker(markers: list[dict[str, Any]], date: str, label: str, y_value: Any, source: str, direction: str, score: Any = None) -> None:
    if not label:
        return
    duplicate_key = (date, label, source)
    existing = {(item["date"], item["label"], item["source"]) for item in markers}
    if duplicate_key in existing:
        return
    markers.append(
        {
            "date": date,
            "label": label[:18],
            "y": json_float(y_value),
            "source": source,
            "direction": direction,
            "score": json_float(score, 2),
        }
    )


def compact_signal_label(source: str, name: str) -> str:
    mapping = {
        "qlib_factor_score": "qlib因子",
        "momentum_20d": "20日动量",
        "volume_ratio_20d": "量比",
        "lumen_total_score": "Lumen总分",
        "hot_rank_score": "人气",
    }
    prefix = {"qlib": "Q", "LumenAlpha": "L", "Eastmoney": "热"}.get(source, source[:2])
    return f"{prefix}:{mapping.get(name, name)}"


def derive_recent_markers(
    df: pd.DataFrame,
    latest_signals: pd.DataFrame | None = None,
    marker_days: int = 5,
    source_prefix: str = "price",
) -> list[dict[str, Any]]:
    if df is None or len(df) < 8:
        return []
    frame = df.sort_values("日期").copy()
    close = pd.to_numeric(frame["收盘"], errors="coerce")
    high = pd.to_numeric(frame["最高"], errors="coerce")
    volume = pd.to_numeric(frame.get("成交量", pd.Series(np.nan, index=frame.index)), errors="coerce")
    frame["_ret"] = close.pct_change()
    frame["_ma20"] = close.rolling(20, min_periods=5).mean()
    frame["_high20_prev"] = high.shift(1).rolling(20, min_periods=5).max()
    frame["_vol20"] = volume.shift(1).rolling(20, min_periods=5).mean()
    markers: list[dict[str, Any]] = []

    recent = frame.tail(marker_days)
    for pos, row in recent.iterrows():
        date = pd.to_datetime(row["日期"]).strftime("%Y-%m-%d")
        ret = row.get("_ret")
        vol20 = row.get("_vol20")
        vol_ratio = row.get("成交量") / vol20 if pd.notna(vol20) and vol20 else np.nan
        if pd.notna(ret) and ret >= 0.07:
            add_marker(markers, date, "强势上涨", row.get("最高"), source_prefix, "bullish", ret * 100)
        if pd.notna(ret) and ret <= -0.05:
            add_marker(markers, date, "风险回撤", row.get("最低"), source_prefix, "bearish", ret * 100)
        if pd.notna(vol_ratio) and vol_ratio >= 1.8 and pd.notna(ret) and ret > 0:
            add_marker(markers, date, "放量上涨", row.get("最高"), source_prefix, "bullish", vol_ratio)
        if pd.notna(row.get("_high20_prev")) and pd.notna(row.get("最高")) and row.get("最高") >= row.get("_high20_prev"):
            add_marker(markers, date, "突破20日高点", row.get("最高"), source_prefix, "bullish", ret * 100 if pd.notna(ret) else None)
        prev_idx = frame.index.get_loc(pos) - 1
        if prev_idx >= 0:
            prev = frame.iloc[prev_idx]
            if pd.notna(row.get("_ma20")) and pd.notna(prev.get("_ma20")) and row.get("收盘") > row.get("_ma20") and prev.get("收盘") <= prev.get("_ma20"):
                add_marker(markers, date, "站上MA20", row.get("收盘"), source_prefix, "bullish")

    if latest_signals is not None and not latest_signals.empty and not frame.empty:
        latest_date = pd.to_datetime(frame.iloc[-1]["日期"]).strftime("%Y-%m-%d")
        g = latest_signals.copy()
        g["_abs"] = pd.to_numeric(g["signal_score"], errors="coerce").abs()
        g = g.sort_values("_abs", ascending=False)
        used_sources = set()
        for _, signal in g.iterrows():
            source = clean_str(signal.get("source_project"))
            if source in used_sources and source in {"qlib", "LumenAlpha"}:
                continue
            if "rank_change" in clean_str(signal.get("signal_name")):
                continue
            used_sources.add(source)
            label = compact_signal_label(source, clean_str(signal.get("signal_name")))
            add_marker(markers, latest_date, label, frame.iloc[-1].get("收盘"), source, clean_str(signal.get("direction", "neutral")), signal.get("signal_score"))
            if len([m for m in markers if m["date"] == latest_date]) >= 3:
                break
    return markers


def build_stock_charts(
    leaders: pd.DataFrame,
    histories: dict[str, pd.DataFrame],
    signal_df: pd.DataFrame,
    chart_days: int,
    marker_days: int,
) -> dict[str, Any]:
    charts: dict[str, Any] = {}
    for _, stock in leaders.head(80).iterrows():
        code = normalize_code(stock["code"])
        df = histories.get(code, pd.DataFrame())
        if df is None or len(df) < 5:
            charts[code] = {"candles": [], "markers": []}
            continue
        signals = signal_df[signal_df["code"].map(normalize_code) == code] if not signal_df.empty else pd.DataFrame()
        charts[code] = {
            "candles": history_to_candles(df, chart_days),
            "markers": derive_recent_markers(df, signals, marker_days, "price"),
        }
    return charts


def build_board_charts(
    detail: pd.DataFrame,
    leaders: pd.DataFrame,
    boards: list[str],
    histories: dict[str, pd.DataFrame],
    chart_days: int,
    marker_days: int,
    leaders_per_board: int,
) -> dict[str, Any]:
    if "code" in leaders.columns:
        leader_lookup = leaders.copy()
        leader_lookup["_norm_code"] = leader_lookup["code"].map(normalize_code)
        leader_lookup = leader_lookup.set_index("_norm_code", drop=False)
    else:
        leader_lookup = pd.DataFrame()
    charts: dict[str, Any] = {}
    for board in boards:
        members = detail[detail["board_path"] == board].sort_values("rank").head(max(leaders_per_board * 2, 12)).copy()
        parts = []
        used_codes = []
        for _, stock in members.iterrows():
            code = normalize_code(stock["code"])
            df = histories.get(code, pd.DataFrame())
            if df is None or len(df) < 8:
                continue
            recent = df.sort_values("日期").tail(chart_days + 20).copy()
            first_close = pd.to_numeric(recent["收盘"], errors="coerce").dropna()
            if first_close.empty or first_close.iloc[0] == 0:
                continue
            base = first_close.iloc[0]
            part = recent[["日期", "开盘", "最高", "最低", "收盘", "成交量"]].copy()
            for col in ["开盘", "最高", "最低", "收盘"]:
                part[col] = pd.to_numeric(part[col], errors="coerce") / base * 100
            part["成交量"] = pd.to_numeric(part["成交量"], errors="coerce")
            parts.append(part)
            used_codes.append(code)
        if parts:
            merged = pd.concat(parts, ignore_index=True)
            board_df = (
                merged.groupby("日期", as_index=False)
                .agg({"开盘": "mean", "最高": "mean", "最低": "mean", "收盘": "mean", "成交量": "mean"})
                .sort_values("日期")
                .tail(chart_days)
            )
        else:
            board_df = pd.DataFrame()

        constituents = []
        for _, stock in members.head(24).iterrows():
            code = normalize_code(stock["code"])
            leader = leader_lookup.loc[code] if not leader_lookup.empty and code in leader_lookup.index else {}
            if isinstance(leader, pd.DataFrame):
                leader = leader.iloc[0]
            constituents.append(
                {
                    "code": code,
                    "name": clean_str(stock.get("name")),
                    "rank": int(stock.get("rank")) if pd.notna(stock.get("rank")) else None,
                    "combined_score": json_float(leader.get("combined_score") if isinstance(leader, pd.Series) else None, 2),
                    "qlib_factor_score": json_float(leader.get("qlib_factor_score") if isinstance(leader, pd.Series) else None, 2),
                    "lumen_score": json_float(leader.get("lumen_score") if isinstance(leader, pd.Series) else None, 2),
                }
            )
        charts[board] = {
            "candles": history_to_candles(board_df, chart_days),
            "markers": derive_recent_markers(board_df, None, marker_days, "sector") if not board_df.empty else [],
            "constituents": constituents,
            "member_codes": used_codes[:16],
        }
    return charts


def build_dashboard_payload(
    detail: pd.DataFrame,
    leaders: pd.DataFrame,
    board_summary: pd.DataFrame,
    curve_df: pd.DataFrame,
    selected_boards: list[str],
    signal_df: pd.DataFrame,
    review: dict[str, Any],
    histories: dict[str, pd.DataFrame],
    chart_days: int,
    marker_days: int,
    leaders_per_board: int,
) -> dict[str, Any]:
    top_leaders = leaders.head(80).copy()
    board_cards = board_summary[board_summary["board_path"].isin(selected_boards)].copy()
    if "sector_trend_score" not in board_cards:
        board_cards["sector_trend_score"] = 50
    board_cards = board_cards.sort_values(["is_tech", "stock_count", "best_rank"], ascending=[False, False, True])
    payload = {
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "review": review,
        "leaders": records_for_json(top_leaders),
        "boards": records_for_json(board_cards),
        "curves": records_for_json(curve_df),
        "signals": records_for_json(signal_df.sort_values("signal_score", ascending=False).head(250)),
        "stockCharts": build_stock_charts(top_leaders, histories, signal_df, chart_days, marker_days),
        "boardCharts": build_board_charts(detail, leaders, selected_boards, histories, chart_days, marker_days, leaders_per_board),
    }
    return payload


def write_latest_copy(path: Path) -> None:
    latest_name = path.name
    latest_name = latest_name.replace(datetime.now().strftime("%Y%m%d"), "latest")
    # Simpler stable latest names are handled by explicit mapping below.


def main() -> int:
    args = parse_args()
    if not args.keep_proxy:
        clear_proxy_env()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "reports").mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    detail, board_summary = read_inputs(Path(args.detail), Path(args.board_summary))
    selected_boards = select_boards(board_summary, args.top_boards)
    selected_stocks = select_stocks(detail, selected_boards, args.leaders_per_board, args.max_stocks)
    histories, history_status = fetch_histories(selected_stocks, output_dir, args.history_days, args.workers, args.refresh_history)
    feature_df = compute_price_features(histories)

    qlib_rows = build_qlib_signal_rows(selected_stocks, feature_df)
    lumen_rows, lumen_summary = build_lumen_signal_rows(selected_stocks, histories)
    popularity_rows = build_popularity_signal_rows(selected_stocks)
    signal_df = pd.DataFrame(qlib_rows + lumen_rows + popularity_rows)

    curve_df, curve_summary = build_sector_curves(detail, selected_boards, histories, args.curve_days, args.leaders_per_board)
    leaders = aggregate_leader_cards(selected_stocks, feature_df, lumen_summary, signal_df, curve_summary)

    board_enriched = board_summary.merge(curve_summary, on="board_path", how="left")
    board_enriched["sector_trend_score"] = (
        pct_rank(board_enriched["sector_ret_5d"], True) * 0.45
        + pct_rank(board_enriched["sector_ret_20d"], True) * 0.55
    ).round(2)

    history_ok = int((history_status["rows"] >= 25).sum())
    history_missing = int(len(history_status) - history_ok)
    known_issues = [
        "当前全 A qlib bin 数据尚未导入；第一版 qlib 信号使用 qlib 表达式兼容公式在 AkShare 历史行情上计算。",
        "科技细分 taxonomy 仍需持续校准，尤其是 其他电子通信 与 消费电子 的边界。",
        "板块时间曲线使用每个板块人气前若干股票等权近似，不等同于正式指数。",
    ]
    if history_missing:
        known_issues.append(f"本轮有 {history_missing} 只股票历史行情未成功拉取，主要表现为历史行情接口错误或无返回；对应个股的 qlib/LumenAlpha 分数会降级。")

    review = {
        "rows_detail": int(len(detail)),
        "tech_rows": int(detail["is_tech"].sum()),
        "selected_boards": len(selected_boards),
        "selected_stocks": int(len(selected_stocks)),
        "history_ok": history_ok,
        "history_total": int(len(history_status)),
        "history_missing": history_missing,
        "unified_signal_rows": int(len(signal_df)),
        "curve_boards": int(curve_df["board_path"].nunique()) if not curve_df.empty else 0,
        "known_issues": known_issues,
    }

    unified_path = output_dir / f"unified_signals_{stamp}.csv"
    leaders_path = output_dir / f"leader_cards_{stamp}.csv"
    leaders_json_path = output_dir / f"leader_cards_{stamp}.json"
    sector_curve_path = output_dir / f"sector_timeseries_{stamp}.csv"
    sector_summary_path = output_dir / f"sector_summary_{stamp}.csv"
    history_status_path = output_dir / f"history_fetch_status_{stamp}.csv"
    review_path = output_dir / "reports" / f"review_report_{stamp}.md"

    signal_df.to_csv(unified_path, index=False, encoding="utf-8-sig")
    leaders.to_csv(leaders_path, index=False, encoding="utf-8-sig")
    leaders_json_path.write_text(json.dumps(records_for_json(leaders), ensure_ascii=False, indent=2), encoding="utf-8")
    curve_df.to_csv(sector_curve_path, index=False, encoding="utf-8-sig")
    board_enriched.to_csv(sector_summary_path, index=False, encoding="utf-8-sig")
    history_status.to_csv(history_status_path, index=False, encoding="utf-8-sig")

    review_md = [
        "# Sector Rotation Output Review",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Data Health",
        f"- Reclassified rows: {review['rows_detail']}",
        f"- Tech rows: {review['tech_rows']}",
        f"- Selected boards: {review['selected_boards']}",
        f"- Selected stocks: {review['selected_stocks']}",
        f"- History OK: {review['history_ok']}/{review['history_total']}",
        f"- History missing: {review['history_missing']}",
        f"- Unified signal rows: {review['unified_signal_rows']}",
        f"- Boards with curves: {review['curve_boards']}",
        "",
        "## Review Findings",
        "- The tech taxonomy is now useful enough for PCB/CPO/liquid-cooling/AI-compute separation.",
        "- LumenAlpha and qlib-style signals are joined through a long-form table with explicit source labels.",
        "- Cross-sectional percentile scoring is used for qlib, LumenAlpha, and sector-trend components to keep sources comparable.",
        "- Some board curves are approximations from hot leaders, not official board indices.",
        "- qlib native data import remains the next major step before serious backtesting.",
        "",
        "## Known Issues",
        "- " + "\n- ".join(review["known_issues"]),
    ]
    review_path.write_text("\n".join(review_md), encoding="utf-8")

    latest_map = {
        unified_path: output_dir / "unified_signals_latest.csv",
        leaders_path: output_dir / "leader_cards_latest.csv",
        leaders_json_path: output_dir / "leader_cards_latest.json",
        sector_curve_path: output_dir / "sector_timeseries_latest.csv",
        sector_summary_path: output_dir / "sector_summary_latest.csv",
        history_status_path: output_dir / "history_fetch_status_latest.csv",
        review_path: output_dir / "reports" / "review_report_latest.md",
    }
    for src, dst in latest_map.items():
        dst.write_bytes(src.read_bytes())

    payload = build_dashboard_payload(
        detail,
        leaders,
        board_enriched,
        curve_df,
        selected_boards,
        signal_df,
        review,
        histories,
        args.chart_days,
        args.marker_days,
        args.leaders_per_board,
    )
    web_data_path = Path(args.web_data)
    web_data_path.parent.mkdir(parents=True, exist_ok=True)
    web_data_path.write_text(
        "window.SECTOR_DASHBOARD_DATA = "
        + json.dumps(payload, ensure_ascii=False, indent=2)
        + ";\n",
        encoding="utf-8",
    )

    print("\nDone.")
    print(f"Unified signals: {unified_path}")
    print(f"Leader cards: {leaders_path}")
    print(f"Sector curves: {sector_curve_path}")
    print(f"Dashboard data: {web_data_path}")
    print(f"Review: {review_path}")
    print("\nTop leaders:")
    print(leaders[["rank", "code", "name", "board_path", "combined_score", "qlib_factor_score", "lumen_score", "top_signals"]].head(12).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
