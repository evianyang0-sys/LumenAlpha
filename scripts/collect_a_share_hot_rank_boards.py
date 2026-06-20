#!/usr/bin/env python3
"""Collect Eastmoney A-share hot ranks and map them to sector boards."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

import akshare as ak
import pandas as pd
import requests


HOT_RANK_URL = "https://emappdata.eastmoney.com/stockrank/getCurrentLatest"
SINA_COUNT_URL = (
    "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
    "Market_Center.getHQNodeStockCount"
)
SINA_DETAIL_URL = (
    "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/"
    "Market_Center.getHQNodeData"
)
DEFAULT_GLOBAL_ID = "786e4c21-70dc-435a-93bb-38"

THREAD_LOCAL = threading.local()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect A-share Eastmoney popularity ranks and board mapping."
    )
    parser.add_argument("--top", type=int, default=2000, help="Top N ranked stocks to save.")
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Concurrent rank workers. Keep this low; Eastmoney may return 403 under bursts.",
    )
    parser.add_argument(
        "--output-dir",
        default="data/a_share_hot_rank",
        help="Directory for generated CSV/JSON files.",
    )
    parser.add_argument(
        "--keep-proxy",
        action="store_true",
        help="Keep HTTP proxy environment variables instead of clearing them.",
    )
    parser.add_argument(
        "--skip-concepts",
        action="store_true",
        help="Only collect industry board mapping.",
    )
    parser.add_argument(
        "--max-stocks",
        type=int,
        default=None,
        help="Debug option: limit how many stocks are ranked.",
    )
    parser.add_argument(
        "--rank-file",
        default=None,
        help="Reuse a previously generated all-ranks CSV and only rebuild board files.",
    )
    parser.add_argument(
        "--reuse-board-file",
        default=None,
        help=(
            "Reuse industry/concept board columns from a previous detail CSV instead of "
            "fetching Sina board membership. Intended for daily refreshes."
        ),
    )
    return parser.parse_args()


def clear_proxy_env() -> None:
    for key in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    ):
        os.environ.pop(key, None)


def make_session() -> requests.Session:
    session = requests.Session()
    session.trust_env = False
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
        }
    )
    return session


def get_thread_session() -> requests.Session:
    session = getattr(THREAD_LOCAL, "session", None)
    if session is None:
        session = make_session()
        THREAD_LOCAL.session = session
    return session


def normalize_code(value: Any) -> str:
    text = str(value).strip()
    digits = "".join(ch for ch in text if ch.isdigit())
    if not digits:
        return ""
    return digits[-6:].zfill(6)


def market_symbol(code: str) -> str:
    if code.startswith("6"):
        return f"SH{code}"
    if code.startswith(("0", "3")):
        return f"SZ{code}"
    if code.startswith(("4", "8", "9")):
        return f"BJ{code}"
    return code


def fetch_code_name(max_stocks: int | None = None) -> pd.DataFrame:
    print("Fetching A-share code/name list...")
    df = ak.stock_info_a_code_name()
    df = df.rename(columns={"code": "code", "name": "name"}).copy()
    df["code"] = df["code"].map(normalize_code)
    df = df[df["code"] != ""].drop_duplicates("code")
    df["market_symbol"] = df["code"].map(market_symbol)
    if max_stocks:
        df = df.head(max_stocks).copy()
    print(f"Loaded {len(df)} stock codes.")
    return df[["code", "market_symbol", "name"]]


def fetch_latest_rank(row: dict[str, Any], retries: int = 3) -> dict[str, Any]:
    symbol = row["market_symbol"]
    payload = {
        "appId": "appId01",
        "globalId": DEFAULT_GLOBAL_ID,
        "marketType": "",
        "srcSecurityCode": symbol,
    }
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            session = get_thread_session()
            response = session.post(HOT_RANK_URL, json=payload, timeout=12)
            if response.status_code == 403:
                time.sleep(1.5 * attempt)
            response.raise_for_status()
            data = response.json().get("data") or {}
            if not data:
                return {
                    **row,
                    "rank": None,
                    "rank_change": None,
                    "his_rank_change": None,
                    "his_rank_change_rank": None,
                    "calc_time": None,
                    "market_all_count": None,
                    "rank_status": "empty",
                }
            return {
                **row,
                "rank": data.get("rank"),
                "rank_change": data.get("rankChange"),
                "his_rank_change": data.get("hisRankChange"),
                "his_rank_change_rank": data.get("hisRankChange_rank"),
                "calc_time": data.get("calcTime"),
                "market_all_count": data.get("marketAllCount"),
                "rank_status": "ok",
            }
        except Exception as exc:  # noqa: BLE001 - keep collection moving.
            last_error = f"{type(exc).__name__}: {exc}"
            time.sleep(0.25 * attempt)
    return {
        **row,
        "rank": None,
        "rank_change": None,
        "his_rank_change": None,
        "his_rank_change_rank": None,
        "calc_time": None,
        "market_all_count": None,
        "rank_status": f"error: {last_error}",
    }


def collect_ranks(stocks: pd.DataFrame, workers: int) -> pd.DataFrame:
    print(f"Fetching Eastmoney latest hot ranks with {workers} workers...")
    started = time.time()
    rows = stocks.to_dict("records")
    results: list[dict[str, Any]] = []
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(fetch_latest_rank, row) for row in rows]
        for future in as_completed(futures):
            results.append(future.result())
            done += 1
            if done % 250 == 0 or done == len(rows):
                elapsed = time.time() - started
                print(f"  ranked {done}/{len(rows)} stocks in {elapsed:.1f}s")

    df = pd.DataFrame(results)
    numeric_cols = ["rank", "rank_change", "his_rank_change", "his_rank_change_rank"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["market_all_count"] = pd.to_numeric(df["market_all_count"], errors="coerce")
    df = df.sort_values(["rank", "code"], na_position="last").reset_index(drop=True)
    ok_count = int(df["rank"].notna().sum())
    print(f"Collected ranks for {ok_count}/{len(df)} stocks.")
    return df


def parse_sina_json(text: str) -> list[dict[str, Any]]:
    try:
        return json.loads(text)
    except Exception:
        pass

    try:
        import demjson3 as demjson  # type: ignore
    except Exception:
        try:
            import demjson  # type: ignore
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("Sina response is not strict JSON and demjson is unavailable") from exc

    return demjson.decode(text)


def fetch_sina_sector_detail(label: str, session: requests.Session) -> pd.DataFrame:
    count_response = session.get(SINA_COUNT_URL, params={"node": label}, timeout=12)
    count_response.raise_for_status()
    raw_total = str(count_response.text).strip()
    try:
        total = int(json.loads(raw_total))
    except Exception:
        total = int(raw_total.strip('"'))
    pages = max(1, math.ceil(total / 80))
    frames: list[pd.DataFrame] = []
    for page in range(1, pages + 1):
        params = {
            "page": str(page),
            "num": "80",
            "sort": "symbol",
            "asc": "1",
            "node": label,
            "symbol": "",
            "_s_r_a": "page",
        }
        response = session.get(SINA_DETAIL_URL, params=params, timeout=12)
        response.raise_for_status()
        data = parse_sina_json(response.text)
        if data:
            frames.append(pd.DataFrame(data))
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    if "code" in df.columns:
        df["code"] = df["code"].map(normalize_code)
    return df


def build_sina_board_map(indicator: str) -> tuple[dict[str, list[str]], pd.DataFrame]:
    print(f"Fetching Sina {indicator} board list and constituents...")
    boards = ak.stock_sector_spot(indicator=indicator)
    session = make_session()
    mapping: dict[str, list[str]] = defaultdict(list)
    summary_rows: list[dict[str, Any]] = []
    for index, board in boards.iterrows():
        label = str(board["label"])
        board_name = str(board["板块"])
        try:
            detail = fetch_sina_sector_detail(label, session)
            member_count = len(detail)
            for code in detail.get("code", pd.Series(dtype=str)).dropna().unique():
                if code:
                    mapping[str(code)].append(board_name)
            summary_rows.append(
                {
                    "board_type": indicator,
                    "board": board_name,
                    "label": label,
                    "member_count": member_count,
                    "fetch_status": "ok",
                }
            )
        except Exception as exc:  # noqa: BLE001 - record partial board failures.
            summary_rows.append(
                {
                    "board_type": indicator,
                    "board": board_name,
                    "label": label,
                    "member_count": None,
                    "fetch_status": f"error: {type(exc).__name__}: {exc}",
                }
            )
        if (index + 1) % 25 == 0 or index + 1 == len(boards):
            print(f"  fetched {index + 1}/{len(boards)} {indicator} boards")

    mapping = {code: sorted(set(names)) for code, names in mapping.items()}
    return mapping, pd.DataFrame(summary_rows)


def enrich_official_industry(df: pd.DataFrame) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    try:
        sz = ak.stock_info_sz_name_code()
        sz = sz.rename(columns={"A股代码": "code", "所属行业": "exchange_industry"})
        sz["code"] = sz["code"].map(normalize_code)
        frames.append(sz[["code", "exchange_industry"]])
    except Exception as exc:  # noqa: BLE001
        print(f"Warning: failed to fetch SZSE industry fallback: {exc}")
    try:
        bj = ak.stock_info_bj_name_code()
        bj = bj.rename(columns={"证券代码": "code", "所属行业": "exchange_industry"})
        bj["code"] = bj["code"].map(normalize_code)
        frames.append(bj[["code", "exchange_industry"]])
    except Exception as exc:  # noqa: BLE001
        print(f"Warning: failed to fetch BSE industry fallback: {exc}")

    if not frames:
        df["exchange_industry"] = ""
        return df

    fallback = pd.concat(frames, ignore_index=True).drop_duplicates("code")
    return df.merge(fallback, on="code", how="left")


def join_boards(
    top_df: pd.DataFrame,
    industry_map: dict[str, list[str]],
    concept_map: dict[str, list[str]] | None,
) -> pd.DataFrame:
    df = top_df.copy()
    df["industry_boards"] = df["code"].map(lambda code: ";".join(industry_map.get(code, [])))
    df["primary_industry"] = df["industry_boards"].map(lambda text: text.split(";")[0] if text else "")
    df = enrich_official_industry(df)
    df["exchange_industry"] = df["exchange_industry"].fillna("")
    df["primary_industry"] = df.apply(
        lambda row: row["primary_industry"] or str(row.get("exchange_industry") or "").strip(),
        axis=1,
    )

    if concept_map is None:
        df["concept_boards"] = ""
        df["primary_concept"] = ""
        df["concept_count"] = 0
    else:
        df["concept_boards"] = df["code"].map(lambda code: ";".join(concept_map.get(code, [])))
        df["primary_concept"] = df["concept_boards"].map(lambda text: text.split(";")[0] if text else "")
        df["concept_count"] = df["concept_boards"].map(
            lambda text: 0 if not text else len(text.split(";"))
        )
    return df


def join_reused_boards(top_df: pd.DataFrame, reuse_board_file: Path) -> pd.DataFrame:
    reuse_cols = [
        "code",
        "industry_boards",
        "primary_industry",
        "exchange_industry",
        "concept_boards",
        "primary_concept",
        "concept_count",
    ]
    previous = pd.read_csv(reuse_board_file, dtype={"code": str})
    previous["code"] = previous["code"].map(normalize_code)
    for col in reuse_cols:
        if col not in previous.columns:
            previous[col] = "" if col != "concept_count" else 0
    previous = previous[reuse_cols].drop_duplicates("code")

    df = top_df.merge(previous, on="code", how="left")
    for col in ["industry_boards", "primary_industry", "exchange_industry", "concept_boards", "primary_concept"]:
        df[col] = df[col].fillna("")
    df["concept_count"] = pd.to_numeric(df["concept_count"], errors="coerce").fillna(0).astype(int)
    df["primary_industry"] = df.apply(
        lambda row: row["primary_industry"] or str(row.get("exchange_industry") or "").strip(),
        axis=1,
    )
    return df


def summarize_boards(df: pd.DataFrame, column: str, board_type: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        boards = [item for item in str(row.get(column, "")).split(";") if item]
        for board in boards:
            rows.append(
                {
                    "board_type": board_type,
                    "board": board,
                    "rank": row["rank"],
                    "code": row["code"],
                    "name": row["name"],
                }
            )
    if not rows:
        return pd.DataFrame(
            columns=["board_type", "board", "stock_count", "best_rank", "avg_rank", "top_stocks"]
        )
    exploded = pd.DataFrame(rows)
    summary = (
        exploded.groupby(["board_type", "board"])
        .agg(stock_count=("code", "count"), best_rank=("rank", "min"), avg_rank=("rank", "mean"))
        .reset_index()
    )
    top_stock_rows = (
        exploded.sort_values(["board_type", "board", "rank"])
        .groupby(["board_type", "board"], as_index=False)
        .head(5)
        .copy()
    )
    top_stock_rows["stock_text"] = top_stock_rows.apply(
        lambda row: f"{row['code']}:{row['name']}#{int(row['rank'])}",
        axis=1,
    )
    top_stocks = (
        top_stock_rows.groupby(["board_type", "board"])["stock_text"]
        .agg(" | ".join)
        .rename("top_stocks")
        .reset_index()
    )
    summary = summary.merge(top_stocks, on=["board_type", "board"], how="left")
    summary = summary.sort_values(["stock_count", "best_rank"], ascending=[False, True])
    summary["avg_rank"] = summary["avg_rank"].round(2)
    return summary


def write_latest_copy(path: Path) -> None:
    latest_name = re.sub(r"_\d{8}_\d{6}(\.[^.]+)$", r"_latest\1", path.name)
    latest = path.with_name(latest_name)
    latest.write_bytes(path.read_bytes())


def main() -> int:
    args = parse_args()
    if not args.keep_proxy:
        clear_proxy_env()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    collected_at = datetime.now().isoformat(timespec="seconds")

    if args.rank_file:
        print(f"Loading rank file: {args.rank_file}")
        ranks = pd.read_csv(args.rank_file, dtype={"code": str, "market_symbol": str})
        ranks["code"] = ranks["code"].map(normalize_code)
        ranks["market_symbol"] = ranks["market_symbol"].astype(str)
        if args.max_stocks:
            ranks = ranks.head(args.max_stocks).copy()
        stocks = ranks[["code", "market_symbol", "name"]].drop_duplicates("code")
        print(f"Loaded {len(ranks)} rank rows from file.")
    else:
        stocks = fetch_code_name(args.max_stocks)
        ranks = collect_ranks(stocks, max(1, args.workers))
    all_ranks_path = output_dir / f"a_share_hot_rank_all_ranks_{stamp}.csv"
    ranks.to_csv(all_ranks_path, index=False, encoding="utf-8-sig")

    ranked = ranks.dropna(subset=["rank"]).copy()
    ranked["rank"] = ranked["rank"].astype(int)
    top_df = ranked.sort_values(["rank", "code"]).head(args.top).copy()
    top_df["collected_at"] = collected_at

    if args.reuse_board_file:
        reuse_board_file = Path(args.reuse_board_file)
        print(f"Reusing board mapping from: {reuse_board_file}")
        enriched = join_reused_boards(top_df, reuse_board_file)
        industry_fetch_summary = pd.DataFrame(
            [
                {
                    "board_type": "reuse",
                    "board": "industry/concept",
                    "label": str(reuse_board_file),
                    "member_count": int(enriched["industry_boards"].astype(str).ne("").sum()),
                    "fetch_status": "reused_board_file",
                }
            ]
        )
        concept_fetch_summary = pd.DataFrame()
    else:
        industry_map, industry_fetch_summary = build_sina_board_map("行业")
        concept_map = None
        concept_fetch_summary = pd.DataFrame()
        if not args.skip_concepts:
            concept_map, concept_fetch_summary = build_sina_board_map("概念")

        enriched = join_boards(top_df, industry_map, concept_map)

    detail_path = output_dir / f"a_share_hot_rank_top{args.top}_boards_{stamp}.csv"
    industry_summary_path = output_dir / f"a_share_hot_rank_top{args.top}_by_industry_{stamp}.csv"
    concept_summary_path = output_dir / f"a_share_hot_rank_top{args.top}_by_concept_{stamp}.csv"
    board_fetch_path = output_dir / f"a_share_board_fetch_summary_{stamp}.csv"
    notes_path = output_dir / f"a_share_hot_rank_notes_{stamp}.json"

    industry_summary = summarize_boards(enriched, "industry_boards", "industry")
    concept_summary = summarize_boards(enriched, "concept_boards", "concept")
    board_fetch_summary = pd.concat(
        [industry_fetch_summary, concept_fetch_summary], ignore_index=True
    )

    enriched.to_csv(detail_path, index=False, encoding="utf-8-sig")
    industry_summary.to_csv(industry_summary_path, index=False, encoding="utf-8-sig")
    concept_summary.to_csv(concept_summary_path, index=False, encoding="utf-8-sig")
    board_fetch_summary.to_csv(board_fetch_path, index=False, encoding="utf-8-sig")

    notes = {
        "requested_top": args.top,
        "collected_top_rows": int(len(enriched)),
        "all_code_rows": int(len(stocks)),
        "ranked_rows": int(ranked.shape[0]),
        "unranked_rows": int(ranks["rank"].isna().sum()),
        "calc_times": sorted(str(x) for x in ranked["calc_time"].dropna().unique()),
        "market_all_count_values": sorted(
            int(x) for x in ranked["market_all_count"].dropna().unique()
        ),
        "collected_at": collected_at,
        "sources": {
            "hot_rank": "Eastmoney emappdata stockrank/getCurrentLatest per stock",
            "industry_boards": "Sina stock sector spot/detail, indicator=行业",
            "concept_boards": "Sina stock sector spot/detail, indicator=概念",
            "code_name": "AkShare stock_info_a_code_name",
            "board_mapping": (
                f"reused from {args.reuse_board_file}"
                if args.reuse_board_file
                else "Sina stock sector spot/detail"
            ),
        },
        "files": {
            "all_ranks": str(all_ranks_path),
            "detail": str(detail_path),
            "industry_summary": str(industry_summary_path),
            "concept_summary": str(concept_summary_path),
            "board_fetch_summary": str(board_fetch_path),
        },
    }
    notes_path.write_text(json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8")

    for path in [
        all_ranks_path,
        detail_path,
        industry_summary_path,
        concept_summary_path,
        board_fetch_path,
        notes_path,
    ]:
        write_latest_copy(path)

    print("\nDone.")
    print(f"Detail: {detail_path}")
    print(f"Industry summary: {industry_summary_path}")
    print(f"Concept summary: {concept_summary_path}")
    print(f"Notes: {notes_path}")
    print("\nTop 10:")
    print(
        enriched[
            ["rank", "code", "market_symbol", "name", "primary_industry", "primary_concept"]
        ]
        .head(10)
        .to_string(index=False)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
