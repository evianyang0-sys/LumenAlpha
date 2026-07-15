#!/usr/bin/env python3
"""Calculate one A-share stock against the current LumenAlpha reference universe."""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lumen_qlib.sector_rotation_pipeline import (
    build_lumen_signal_rows,
    build_popularity_signal_rows,
    build_qlib_signal_rows,
    build_stock_charts,
    clear_proxy_env,
    compute_price_features,
    fetch_history_one,
    normalize_code,
    pct_rank,
    records_for_json,
)


RANKS_PATH = ROOT / "data/a_share_hot_rank/a_share_hot_rank_all_ranks_latest.csv"
DETAIL_PATH = ROOT / "data/a_share_hot_rank/a_share_hot_rank_top2000_tech_reclassified_latest.csv"
REFERENCE_PATH = ROOT / "data/sector_rotation/leader_cards_latest.csv"
SECTOR_PATH = ROOT / "data/sector_rotation/sector_summary_latest.csv"
HISTORY_CACHE = ROOT / "data/sector_rotation/cache"
RESULT_CACHE = ROOT / "data/sector_rotation/on_demand"
RAW_FEATURES = ["ret_5d", "ret_20d", "ma20_bias", "volume_ratio_20", "volatility_20"]


class StockLookupError(ValueError):
    def __init__(self, message: str, candidates: list[dict[str, str]] | None = None):
        super().__init__(message)
        self.candidates = candidates or []


def finite_float(value: Any, default: float | None = None) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def clean_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): clean_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [clean_json(item) for item in value]
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return float(value) if math.isfinite(float(value)) else None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"缺少计算数据：{path.name}")
    frame = pd.read_csv(path, dtype={"code": str})
    if "code" in frame:
        frame["code"] = frame["code"].map(normalize_code)
    return frame


def candidate_rows(frame: pd.DataFrame) -> list[dict[str, str]]:
    rows = frame.copy()
    rows["_rank"] = pd.to_numeric(rows.get("rank"), errors="coerce")
    rows = rows.sort_values("_rank", na_position="last").head(8)
    return [{"code": str(row["code"]), "name": str(row.get("name") or "")} for _, row in rows.iterrows()]


def resolve_stock(query: str, ranks_path: Path = RANKS_PATH, detail_path: Path = DETAIL_PATH) -> dict[str, Any]:
    keyword = str(query or "").strip()
    if not keyword or len(keyword) > 20:
        raise StockLookupError("请输入完整股票名称或6位代码")

    ranks = read_csv(ranks_path).drop_duplicates("code", keep="first")
    digits = "".join(char for char in keyword if char.isdigit())
    if len(digits) == 6:
        matches = ranks[ranks["code"] == digits]
    else:
        names = ranks["name"].fillna("").astype(str)
        exact = ranks[names == keyword]
        matches = exact if not exact.empty else ranks[names.str.contains(keyword, regex=False)]

    if matches.empty:
        raise StockLookupError("未在当前A股名录中找到该股票")
    if len(matches) > 1:
        raise StockLookupError("匹配到多只股票，请选择具体代码", candidate_rows(matches))

    stock = matches.iloc[0].dropna().to_dict()
    detail = read_csv(detail_path)
    classified = detail[detail["code"] == stock["code"]]
    if not classified.empty:
        stock.update(classified.iloc[0].dropna().to_dict())
    stock.setdefault("board_l1", "")
    stock.setdefault("board_l2", "")
    stock.setdefault("board_l3", "未分类")
    stock.setdefault("board_path", "未分类")
    stock["rank"] = finite_float(stock.get("rank"))
    stock["market_all_count"] = finite_float(stock.get("market_all_count"), len(ranks))
    return clean_json(stock)


def rank_price_feature(raw: dict[str, Any], reference: pd.DataFrame) -> dict[str, Any]:
    code = normalize_code(raw.get("code"))
    available = [column for column in ["code", *RAW_FEATURES] if column in reference.columns]
    universe = reference[available].copy() if available else pd.DataFrame(columns=["code", *RAW_FEATURES])
    if "code" not in universe:
        universe["code"] = ""
    universe["code"] = universe["code"].map(normalize_code)
    universe = universe[universe["code"] != code]
    target = {"code": code, **{column: raw.get(column) for column in RAW_FEATURES}}
    universe = pd.concat([universe, pd.DataFrame([target])], ignore_index=True)
    for column in RAW_FEATURES:
        if column not in universe:
            universe[column] = np.nan
        universe[column] = pd.to_numeric(universe[column], errors="coerce")

    universe["qlib_mom_5_rank"] = pct_rank(universe["ret_5d"], True)
    universe["qlib_mom_20_rank"] = pct_rank(universe["ret_20d"], True)
    universe["qlib_ma20_bias_rank"] = pct_rank(universe["ma20_bias"], True)
    universe["qlib_volume_rank"] = pct_rank(universe["volume_ratio_20"], True)
    universe["qlib_volatility_rank"] = pct_rank(universe["volatility_20"], False)
    universe["qlib_factor_score"] = (
        0.30 * universe["qlib_mom_5_rank"]
        + 0.30 * universe["qlib_mom_20_rank"]
        + 0.20 * universe["qlib_ma20_bias_rank"]
        + 0.15 * universe["qlib_volume_rank"]
        + 0.05 * universe["qlib_volatility_rank"]
    ).round(2)
    ranked = universe.iloc[-1].to_dict()
    return clean_json({**raw, **ranked})


def lumen_percentile(value: Any, reference: pd.DataFrame, code: str = "") -> float:
    number = finite_float(value)
    if number is None or "lumen_score" not in reference:
        return 50.0
    universe = reference
    if code and "code" in universe:
        universe = universe[universe["code"].map(normalize_code) != normalize_code(code)]
    scores = pd.to_numeric(universe["lumen_score"], errors="coerce").dropna().tolist()
    scores.append(number)
    return round(float(pct_rank(pd.Series(scores), True).iloc[-1]), 2)


def sector_snapshot(stock: dict[str, Any], sectors: pd.DataFrame) -> tuple[dict[str, Any], bool]:
    if "board_path" not in sectors:
        return {"sector_ret_5d": None, "sector_ret_20d": None, "sector_trend_score": 50.0}, False
    matched = sectors[sectors["board_path"].fillna("").astype(str) == str(stock.get("board_path") or "")]
    if matched.empty:
        return {"sector_ret_5d": None, "sector_ret_20d": None, "sector_trend_score": 50.0}, False
    row = matched.iloc[0]
    score = finite_float(row.get("sector_trend_score"))
    return {
        "sector_ret_5d": finite_float(row.get("sector_ret_5d")),
        "sector_ret_20d": finite_float(row.get("sector_ret_20d")),
        "sector_trend_score": score if score is not None else 50.0,
    }, score is not None


def calculate_stock(
    stock: dict[str, Any],
    history: pd.DataFrame,
    history_status: str,
    reference: pd.DataFrame,
    sectors: pd.DataFrame,
) -> dict[str, Any]:
    code = normalize_code(stock.get("code"))
    if len(history) < 25:
        raise RuntimeError("有效日线不足25个交易日，暂时无法计算")

    raw = compute_price_features({code: history}).iloc[0].to_dict()
    feature = rank_price_feature(raw, reference)
    selected = pd.DataFrame([{**stock, "code": code}])
    feature_frame = pd.DataFrame([feature])
    qlib_rows = build_qlib_signal_rows(selected, feature_frame)
    lumen_rows, lumen_summary = build_lumen_signal_rows(selected, {code: history})
    popularity_rows = build_popularity_signal_rows(selected) if stock.get("rank") is not None else []
    signal_frame = pd.DataFrame(qlib_rows + lumen_rows + popularity_rows)
    latest_date = pd.to_datetime(history["日期"].max()).strftime("%Y-%m-%d")
    if not signal_frame.empty:
        signal_frame["date"] = latest_date

    lumen = lumen_summary.iloc[0].to_dict() if not lumen_summary.empty else {}
    lumen_score = finite_float(lumen.get("lumen_score"))
    sector, has_sector = sector_snapshot(stock, sectors)
    rank = finite_float(stock.get("rank"))
    market_all = finite_float(stock.get("market_all_count"), 5528.0) or 5528.0
    popularity = 100 * (1 - (rank - 1) / max(market_all, 1)) if rank is not None else 50.0
    lumen_norm = lumen_percentile(lumen_score, reference, code)
    combined = round(
        0.35 * popularity
        + 0.30 * float(finite_float(feature.get("qlib_factor_score"), 50.0))
        + 0.22 * lumen_norm
        + 0.13 * float(sector["sector_trend_score"]),
        2,
    )

    top_signals = ""
    if not signal_frame.empty:
        ranked_signals = signal_frame.assign(
            _abs=pd.to_numeric(signal_frame["signal_score"], errors="coerce").abs()
        ).sort_values("_abs", ascending=False).head(5)
        top_signals = " | ".join(
            f"{row['source_project']}:{row['signal_name']}({float(row['signal_score']):.1f})"
            for _, row in ranked_signals.iterrows()
        )

    components = {
        "price": True,
        "lumen": lumen_score is not None,
        "popularity": rank is not None,
        "sector": has_sector,
    }
    reference_count = int(len(reference))
    note_parts = [f"量价评分相对当前{reference_count}只参考样本计算"]
    note_parts.append("人气与板块使用最近系统快照")
    missing = [label for key, label in [("lumen", "技术形态"), ("popularity", "人气"), ("sector", "板块")] if not components[key]]
    if missing:
        note_parts.append(f"{','.join(missing)}数据不足，按中性值处理")
    quality = {
        "historySource": str(history_status or "unknown").split(":", 1)[0],
        "historyRows": int(len(history)),
        "referenceCount": reference_count,
        "components": components,
        "note": "；".join(note_parts),
    }

    leader = {
        **stock,
        **feature,
        **lumen,
        **sector,
        "code": code,
        "popularity_score": round(popularity, 2),
        "lumen_score": lumen_score,
        "lumen_score_norm": lumen_norm,
        "combined_score": combined,
        "top_signals": top_signals,
        "on_demand": True,
        "calculation_note": quality["note"],
        "calculation_quality": quality,
    }
    chart = build_stock_charts(pd.DataFrame([leader]), {code: history}, signal_frame, 30, 5)[code]
    return clean_json(
        {
            "ok": True,
            "cached": False,
            "generatedAt": datetime.now().isoformat(timespec="seconds"),
            "latestDate": latest_date,
            "leader": leader,
            "chart": chart,
            "signals": records_for_json(signal_frame),
            "quality": quality,
        }
    )


def calculate_query(query: str, max_age_seconds: int) -> dict[str, Any]:
    stock = resolve_stock(query)
    code = normalize_code(stock["code"])
    RESULT_CACHE.mkdir(parents=True, exist_ok=True)
    result_path = RESULT_CACHE / f"{code}.json"
    if result_path.exists() and time.time() - result_path.stat().st_mtime <= max(0, max_age_seconds):
        cached = json.loads(result_path.read_text(encoding="utf-8"))
        cached["cached"] = True
        return cached

    HISTORY_CACHE.mkdir(parents=True, exist_ok=True)
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=220)).strftime("%Y%m%d")
    _, history, status = fetch_history_one(code, start_date, end_date, HISTORY_CACHE, False)
    if history is None or len(history) < 25:
        raise RuntimeError(f"行情拉取失败：{status or '无有效数据'}")

    reference = read_csv(REFERENCE_PATH)
    sectors = read_csv(SECTOR_PATH)
    payload = calculate_stock(stock, history, status, reference, sectors)
    temp_path = result_path.with_suffix(f".{os.getpid()}.tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    temp_path.replace(result_path)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Calculate a single stock for the dashboard.")
    parser.add_argument("--query", required=True, help="Exact stock name or 6-digit code.")
    parser.add_argument("--max-age", type=int, default=1800, help="Result cache lifetime in seconds.")
    parser.add_argument("--keep-proxy", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.keep_proxy:
        clear_proxy_env()
    try:
        payload = calculate_query(args.query, args.max_age)
    except StockLookupError as error:
        payload = {
            "ok": False,
            "error": str(error),
            "errorCode": "AMBIGUOUS" if error.candidates else "NOT_FOUND",
            "candidates": error.candidates,
        }
    except Exception as error:  # noqa: BLE001
        payload = {"ok": False, "error": str(error)}
    print(json.dumps(clean_json(payload), ensure_ascii=False, allow_nan=False))
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
