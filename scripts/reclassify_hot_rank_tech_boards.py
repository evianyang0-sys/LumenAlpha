#!/usr/bin/env python3
"""Reclassify hot-rank stocks into tech-aware hierarchical boards."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import akshare as ak
import pandas as pd
import py_mini_racer
import requests
from bs4 import BeautifulSoup

from akshare.stock_feature.stock_board_concept_ths import _get_file_content_ths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Classify hot-rank stocks with hierarchical tech boards."
    )
    parser.add_argument(
        "--input",
        default="data/a_share_hot_rank/a_share_hot_rank_top2000_boards_latest.csv",
        help="Input hot-rank detail CSV.",
    )
    parser.add_argument(
        "--taxonomy",
        default="config/tech_board_taxonomy.json",
        help="Tech board taxonomy JSON.",
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
        "--sleep",
        type=float,
        default=0.15,
        help="Sleep seconds between THS page requests.",
    )
    parser.add_argument(
        "--reuse-classification-file",
        default=None,
        help=(
            "Reuse tech board classification columns from a previous reclassified CSV. "
            "Missing codes fall back to local industry rules without remote THS fetches."
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


def normalize_code(value: Any) -> str:
    text = str(value).strip()
    digits = "".join(ch for ch in text if ch.isdigit())
    if not digits:
        return ""
    return digits[-6:].zfill(6)


def load_taxonomy(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_ths_headers() -> dict[str, str]:
    js_code = py_mini_racer.MiniRacer()
    js_code.eval(_get_file_content_ths("ths.js"))
    v_code = js_code.call("v")
    return {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
        ),
        "Cookie": f"v={v_code}",
    }


def fetch_concept_code_map() -> dict[str, str]:
    df = ak.stock_board_concept_name_ths()
    return {str(row["name"]): str(row["code"]) for _, row in df.iterrows()}


def parse_ths_member_rows(html: str) -> tuple[list[dict[str, str]], int | None]:
    soup = BeautifulSoup(html, "lxml")
    rows: list[dict[str, str]] = []
    for tr in soup.select("table tbody tr"):
        cells = [td.get_text(strip=True) for td in tr.find_all("td")]
        if len(cells) < 3:
            continue
        code = normalize_code(cells[1])
        name = cells[2]
        if code:
            rows.append({"code": code, "name": name})

    page_count = None
    page_info = soup.find("span", {"class": "page_info"})
    if page_info:
        match = re.search(r"/(\d+)", page_info.get_text(strip=True))
        if match:
            page_count = int(match.group(1))
    return rows, page_count


def fetch_ths_concept_members(
    board_name: str,
    board_code: str,
    sleep_seconds: float,
) -> tuple[pd.DataFrame, str]:
    headers = build_ths_headers()

    def get(url: str) -> requests.Response:
        nonlocal headers
        last_response: requests.Response | None = None
        for attempt in range(3):
            response = requests.get(url, headers=headers, timeout=15)
            last_response = response
            if response.status_code != 401:
                response.raise_for_status()
                return response
            headers = build_ths_headers()
            time.sleep(0.3 * (attempt + 1))
        assert last_response is not None
        last_response.raise_for_status()
        return last_response

    base_url = f"http://q.10jqka.com.cn/gn/detail/code/{board_code}/"
    response = get(base_url)
    rows, page_count = parse_ths_member_rows(response.text)
    page_count = page_count or 1
    status = "ok"

    for page in range(2, page_count + 1):
        url = f"{base_url}field/199112/order/desc/page/{page}/ajax/1/"
        try:
            response = get(url)
            page_rows, _ = parse_ths_member_rows(response.text)
            rows.extend(page_rows)
        except Exception as exc:  # noqa: BLE001 - keep useful partial pages.
            status = f"partial_page_{page}: {type(exc).__name__}: {exc}"
            break
        if sleep_seconds:
            time.sleep(sleep_seconds)

    df = pd.DataFrame(rows).drop_duplicates("code")
    if df.empty:
        return pd.DataFrame(columns=["code", "name", "source_board"]), status
    df["source_board"] = board_name
    return df[["code", "name", "source_board"]], status


def collect_theme_members(
    taxonomy: dict[str, Any],
    sleep_seconds: float,
) -> tuple[dict[str, list[dict[str, Any]]], pd.DataFrame]:
    print("Fetching THS concept board membership for tech taxonomy...")
    concept_codes = fetch_concept_code_map()
    hits: dict[str, list[dict[str, Any]]] = defaultdict(list)
    fetch_rows: list[dict[str, Any]] = []

    source_board_rules: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for theme in taxonomy["themes"]:
        for board in theme["source_boards"]:
            source_board_rules[board].append(theme)

    for index, (board, rules) in enumerate(source_board_rules.items(), start=1):
        board_code = concept_codes.get(board) or taxonomy.get("board_code_overrides", {}).get(board)
        if not board_code:
            fetch_rows.append(
                {
                    "source_board": board,
                    "source_code": "",
                    "member_count": 0,
                    "fetch_status": "missing_board_name",
                }
            )
            continue
        try:
            members, status = fetch_ths_concept_members(board, board_code, sleep_seconds)
            for _, member in members.iterrows():
                for rule in rules:
                    hits[member["code"]].append(
                        {
                            "l2": rule["l2"],
                            "l3": rule["l3"],
                            "priority": int(rule.get("priority", 50)),
                            "source_board": board,
                            "source": "ths",
                        }
                    )
            fetch_rows.append(
                {
                    "source_board": board,
                    "source_code": board_code,
                    "member_count": int(len(members)),
                    "fetch_status": status,
                }
            )
        except Exception as exc:  # noqa: BLE001 - record and keep going.
            fetch_rows.append(
                {
                    "source_board": board,
                    "source_code": board_code,
                    "member_count": 0,
                    "fetch_status": f"error: {type(exc).__name__}: {exc}",
                }
            )
        print(f"  fetched {index}/{len(source_board_rules)} tech source boards")

    for code, manual_hits in taxonomy.get("manual_stock_tags", {}).items():
        for hit in manual_hits:
            hits[normalize_code(code)].append(
                {
                    "l2": hit["l2"],
                    "l3": hit["l3"],
                    "priority": int(hit.get("priority", 1)),
                    "source_board": hit.get("source_board", "manual"),
                    "source": "manual",
                }
            )

    return hits, pd.DataFrame(fetch_rows)


def industry_fallback(row: pd.Series, taxonomy: dict[str, Any]) -> dict[str, Any] | None:
    text = " ".join(
        str(row.get(col, "") or "")
        for col in ["primary_industry", "industry_boards", "exchange_industry", "name"]
    )
    for fallback in taxonomy.get("tech_industry_fallbacks", []):
        if any(keyword in text for keyword in fallback["keywords"]):
            return {
                "l2": fallback["l2"],
                "l3": fallback["l3"],
                "priority": int(fallback.get("priority", 95)),
                "source_board": "industry_fallback",
                "source": "industry_fallback",
            }
    return None


def choose_board(
    row: pd.Series,
    taxonomy: dict[str, Any],
    hits_by_code: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    code = normalize_code(row["code"])
    hits = list(hits_by_code.get(code, []))
    fallback = industry_fallback(row, taxonomy)
    if fallback:
        hits.append(fallback)

    if hits:
        hits = sorted(hits, key=lambda item: (item["priority"], item["l2"], item["l3"]))
        primary = hits[0]
        l2_values = sorted({hit["l2"] for hit in hits}, key=lambda value: min(h["priority"] for h in hits if h["l2"] == value))
        l3_values = sorted({hit["l3"] for hit in hits}, key=lambda value: min(h["priority"] for h in hits if h["l3"] == value))
        source_boards = sorted({hit["source_board"] for hit in hits}, key=lambda value: min(h["priority"] for h in hits if h["source_board"] == value))
        return {
            "is_tech": True,
            "board_l1": taxonomy.get("tech_l1", "科技"),
            "board_l2": primary["l2"],
            "board_l3": primary["l3"],
            "board_path": f"{taxonomy.get('tech_l1', '科技')}>{primary['l2']}>{primary['l3']}",
            "all_tech_l2": ";".join(l2_values),
            "all_tech_l3": ";".join(l3_values),
            "tech_source_boards": ";".join(source_boards),
            "classification_reason": primary["source"],
        }

    board_l1 = str(row.get("primary_industry", "") or "").strip()
    if not board_l1 or board_l1.lower() == "nan":
        board_l1 = str(row.get("exchange_industry", "") or "").strip()
    if not board_l1 or board_l1.lower() == "nan":
        board_l1 = "未分类"
    return {
        "is_tech": False,
        "board_l1": board_l1,
        "board_l2": "",
        "board_l3": "",
        "board_path": board_l1,
        "all_tech_l2": "",
        "all_tech_l3": "",
        "tech_source_boards": "",
        "classification_reason": "non_tech_primary_industry",
    }


def reuse_classification(
    df: pd.DataFrame,
    taxonomy: dict[str, Any],
    reuse_file: Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    class_cols = [
        "code",
        "is_tech",
        "board_l1",
        "board_l2",
        "board_l3",
        "board_path",
        "all_tech_l2",
        "all_tech_l3",
        "tech_source_boards",
        "classification_reason",
    ]
    previous = pd.read_csv(reuse_file, dtype={"code": str})
    previous["code"] = previous["code"].map(normalize_code)
    for col in class_cols:
        if col not in previous.columns:
            previous[col] = ""
    previous = previous[class_cols].drop_duplicates("code")

    out = df.merge(previous, on="code", how="left")
    missing = out["board_path"].isna() | out["board_path"].astype(str).str.strip().isin(["", "nan"])
    if missing.any():
        fallback = out[missing].apply(lambda row: choose_board(row, taxonomy, {}), axis=1)
        fallback_df = pd.DataFrame(list(fallback), index=out[missing].index)
        for col in class_cols:
            if col == "code":
                continue
            out.loc[missing, col] = fallback_df[col]

    for col in [c for c in class_cols if c not in {"code", "is_tech"}]:
        out[col] = out[col].fillna("")
    out["is_tech"] = out["is_tech"].map(lambda value: str(value).lower() in {"true", "1", "1.0"})
    fetch_summary = pd.DataFrame(
        [
            {
                "source_board": "reuse_classification_file",
                "source_code": str(reuse_file),
                "member_count": int((~missing).sum()),
                "fetch_status": "reused_classification_file",
            },
            {
                "source_board": "local_industry_fallback",
                "source_code": "",
                "member_count": int(missing.sum()),
                "fetch_status": "fallback_for_missing_codes",
            },
        ]
    )
    return out, fetch_summary


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    summary = (
        df.groupby(["board_path", "board_l1", "board_l2", "board_l3", "is_tech"], dropna=False)
        .agg(stock_count=("code", "count"), best_rank=("rank", "min"), avg_rank=("rank", "mean"))
        .reset_index()
    )

    top_rows = (
        df.sort_values(["board_path", "rank"])
        .groupby("board_path", as_index=False)
        .head(8)
        .copy()
    )
    top_rows["stock_text"] = top_rows.apply(
        lambda row: f"{row['code']}:{row['name']}#{int(row['rank'])}",
        axis=1,
    )
    top_stocks = (
        top_rows.groupby("board_path")["stock_text"]
        .agg(" | ".join)
        .rename("top_stocks")
        .reset_index()
    )
    summary = summary.merge(top_stocks, on="board_path", how="left")
    summary["avg_rank"] = summary["avg_rank"].round(2)
    return summary.sort_values(["is_tech", "stock_count", "best_rank"], ascending=[False, False, True])


def write_latest_copy(path: Path) -> None:
    latest_name = re.sub(r"_\d{8}_\d{6}(\.[^.]+)$", r"_latest\1", path.name)
    path.with_name(latest_name).write_bytes(path.read_bytes())


def main() -> int:
    args = parse_args()
    if not args.keep_proxy:
        clear_proxy_env()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    taxonomy = load_taxonomy(Path(args.taxonomy))
    df = pd.read_csv(args.input, dtype={"code": str})
    df["code"] = df["code"].map(normalize_code)
    df["rank"] = pd.to_numeric(df["rank"], errors="coerce")
    print(f"Loaded {len(df)} hot-rank rows from {args.input}")

    if args.reuse_classification_file:
        reuse_file = Path(args.reuse_classification_file)
        print(f"Reusing tech classification from: {reuse_file}")
        out, fetch_summary = reuse_classification(df, taxonomy, reuse_file)
    else:
        hits_by_code, fetch_summary = collect_theme_members(taxonomy, args.sleep)
        classifications = df.apply(lambda row: choose_board(row, taxonomy, hits_by_code), axis=1)
        class_df = pd.DataFrame(list(classifications))
        out = pd.concat([df, class_df], axis=1)
    out["classified_at"] = datetime.now().isoformat(timespec="seconds")

    detail_path = output_dir / f"a_share_hot_rank_top2000_tech_reclassified_{stamp}.csv"
    summary_path = output_dir / f"a_share_hot_rank_top2000_by_designed_board_{stamp}.csv"
    fetch_path = output_dir / f"a_share_hot_rank_tech_source_fetch_{stamp}.csv"
    notes_path = output_dir / f"a_share_hot_rank_tech_reclass_notes_{stamp}.json"

    board_summary = summarize(out)
    out.to_csv(detail_path, index=False, encoding="utf-8-sig")
    board_summary.to_csv(summary_path, index=False, encoding="utf-8-sig")
    fetch_summary.to_csv(fetch_path, index=False, encoding="utf-8-sig")

    notes = {
        "input": args.input,
        "taxonomy": args.taxonomy,
        "rows": int(len(out)),
        "tech_rows": int(out["is_tech"].sum()),
        "non_tech_rows": int((~out["is_tech"]).sum()),
        "tech_l2_counts": out[out["is_tech"]]["board_l2"].value_counts().to_dict(),
        "source_fetch_status": fetch_summary["fetch_status"].value_counts().to_dict(),
        "classification_mapping": (
            f"reused from {args.reuse_classification_file}"
            if args.reuse_classification_file
            else "remote THS concept membership + local taxonomy"
        ),
        "files": {
            "detail": str(detail_path),
            "summary": str(summary_path),
            "source_fetch": str(fetch_path),
        },
    }
    notes_path.write_text(json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8")

    for path in [detail_path, summary_path, fetch_path, notes_path]:
        write_latest_copy(path)

    print("\nDone.")
    print(f"Detail: {detail_path}")
    print(f"Summary: {summary_path}")
    print(f"Source fetch: {fetch_path}")
    print("\nSample:")
    sample_names = ["胜宏科技", "工业富联", "天孚通信", "英维克"]
    sample = out[out["name"].isin(sample_names)]
    print(
        sample[
            [
                "rank",
                "code",
                "name",
                "board_l1",
                "board_l2",
                "board_l3",
                "tech_source_boards",
                "classification_reason",
            ]
        ].to_string(index=False)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
