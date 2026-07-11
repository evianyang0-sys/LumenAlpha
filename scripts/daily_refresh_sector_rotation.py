#!/usr/bin/env python3
"""Daily refresh entrypoint for the sector-rotation dashboard and report.

The daily path is deliberately cache-first:

- refresh Eastmoney popularity ranks;
- reuse board membership and tech classification from the latest full refresh;
- incrementally update stock history;
- rebuild unified signals, dashboard data, and a human-readable analysis report.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
HOT_DIR = DATA_DIR / "a_share_hot_rank"
ROTATION_DIR = DATA_DIR / "sector_rotation"
REPORT_DIR = ROTATION_DIR / "reports"
WEB_DIR = ROOT / "web" / "sector_rotation_dashboard"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh sector rotation data and reports.")
    parser.add_argument(
        "--mode",
        choices=["daily", "weekly", "pipeline-only", "analysis-only"],
        default="daily",
        help="daily reuses board/classification caches; weekly refreshes board/classification sources.",
    )
    parser.add_argument("--python", default=sys.executable, help="Python executable used to run project scripts.")
    parser.add_argument("--top", type=int, default=2000, help="Hot-rank rows to keep.")
    parser.add_argument("--rank-workers", type=int, default=2, help="Workers for Eastmoney hot-rank collection.")
    parser.add_argument("--pipeline-workers", type=int, default=1, help="Workers for stock history fetches.")
    parser.add_argument("--history-days", type=int, default=180, help="Calendar days of stock history to keep.")
    parser.add_argument("--top-boards", type=int, default=20, help="Boards rendered in the dashboard.")
    parser.add_argument("--leaders-per-board", type=int, default=8, help="Leaders selected per board.")
    parser.add_argument("--max-stocks", type=int, default=180, help="Max selected stocks for factor/signals.")
    parser.add_argument("--classification-sleep", type=float, default=0.15, help="Sleep between THS requests in weekly mode.")
    parser.add_argument("--keep-proxy", action="store_true", help="Keep proxy environment variables in child scripts.")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without running them.")
    return parser.parse_args()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def as_float(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float("nan")
    return number if math.isfinite(number) else float("nan")


def as_int(value: Any) -> int | None:
    number = as_float(value)
    return int(number) if math.isfinite(number) else None


def fmt_num(value: Any, digits: int = 1) -> str:
    number = as_float(value)
    return "NA" if not math.isfinite(number) else f"{number:.{digits}f}"


def fmt_pct(value: Any) -> str:
    number = as_float(value)
    return "NA" if not math.isfinite(number) else f"{number * 100:.1f}%"


def short_board(board_path: str) -> str:
    parts = [part for part in str(board_path).split(">") if part]
    return parts[-1] if parts else str(board_path or "未分类")


def md_cell(value: Any, limit: int | None = None) -> str:
    text = str(value or "").replace("\n", " ").replace("|", "/").strip()
    if limit and len(text) > limit:
        return text[: limit - 1] + "…"
    return text


def run_step(name: str, cmd: list[str], log_dir: Path, dry_run: bool) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    display = " ".join(cmd)
    print(f"\n[{name}] {display}")
    log_path = log_dir / f"{name}.log"
    if dry_run:
        log_path.write_text(display + "\n", encoding="utf-8")
        return
    started = time.time()
    result = subprocess.run(
        cmd,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    elapsed = time.time() - started
    log_path.write_text(
        f"$ {display}\n\n# elapsed={elapsed:.1f}s exit_code={result.returncode}\n\n"
        f"## stdout\n{result.stdout}\n\n## stderr\n{result.stderr}\n",
        encoding="utf-8",
    )
    if result.stdout:
        print(result.stdout[-3000:])
    if result.returncode != 0:
        if result.stderr:
            print(result.stderr[-3000:])
        raise RuntimeError(f"{name} failed with exit code {result.returncode}; see {log_path}")


def build_collect_cmd(args: argparse.Namespace) -> list[str]:
    cmd = [
        args.python,
        "scripts/collect_a_share_hot_rank_boards.py",
        "--top",
        str(args.top),
        "--workers",
        str(args.rank_workers),
    ]
    reuse_board_file = HOT_DIR / f"a_share_hot_rank_top{args.top}_boards_latest.csv"
    if args.mode == "daily" and reuse_board_file.exists():
        cmd.extend(["--reuse-board-file", str(reuse_board_file)])
    if args.keep_proxy:
        cmd.append("--keep-proxy")
    return cmd


def build_reclassify_cmd(args: argparse.Namespace) -> list[str]:
    input_path = HOT_DIR / f"a_share_hot_rank_top{args.top}_boards_latest.csv"
    cmd = [
        args.python,
        "scripts/reclassify_hot_rank_tech_boards.py",
        "--input",
        str(input_path),
        "--sleep",
        str(args.classification_sleep),
    ]
    reuse_classification_file = HOT_DIR / f"a_share_hot_rank_top{args.top}_tech_reclassified_latest.csv"
    if args.mode == "daily" and reuse_classification_file.exists():
        cmd.extend(["--reuse-classification-file", str(reuse_classification_file)])
    if args.keep_proxy:
        cmd.append("--keep-proxy")
    return cmd


def build_pipeline_cmd(args: argparse.Namespace) -> list[str]:
    cmd = [
        args.python,
        "lumen_qlib/sector_rotation_pipeline.py",
        "--history-days",
        str(args.history_days),
        "--top-boards",
        str(args.top_boards),
        "--leaders-per-board",
        str(args.leaders_per_board),
        "--max-stocks",
        str(args.max_stocks),
        "--workers",
        str(args.pipeline_workers),
    ]
    if args.keep_proxy:
        cmd.append("--keep-proxy")
    return cmd


def classify_signal_confluence(row: dict[str, str]) -> str:
    tags = []
    if as_float(row.get("qlib_factor_score")) >= 60:
        tags.append("Q")
    if as_float(row.get("lumen_score")) >= 7:
        tags.append("L")
    if as_float(row.get("popularity_score")) >= 98:
        tags.append("热")
    if as_float(row.get("sector_trend_score")) >= 70:
        tags.append("板")
    return "+".join(tags) if tags else "-"


def generate_analysis_report(stamp: str) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    notes = read_json(HOT_DIR / "a_share_hot_rank_notes_latest.json")
    reclass_notes = read_json(HOT_DIR / "a_share_hot_rank_tech_reclass_notes_latest.json")
    review_text = (REPORT_DIR / "review_report_latest.md").read_text(encoding="utf-8") if (REPORT_DIR / "review_report_latest.md").exists() else ""
    boards = read_csv_rows(ROTATION_DIR / "sector_summary_latest.csv")
    leaders = read_csv_rows(ROTATION_DIR / "leader_cards_latest.csv")
    history_rows = read_csv_rows(ROTATION_DIR / "history_fetch_status_latest.csv")
    signal_rows = read_csv_rows(ROTATION_DIR / "unified_signals_latest.csv")

    for board in boards:
        board["_score"] = as_float(board.get("sector_trend_score"))
        board["_ret5"] = as_float(board.get("sector_ret_5d"))
        board["_ret20"] = as_float(board.get("sector_ret_20d"))
        board["_is_tech"] = str(board.get("is_tech")).lower() in {"true", "1", "1.0"}
    boards_with_score = [board for board in boards if math.isfinite(board["_score"])]
    tech_boards = [board for board in boards_with_score if board["_is_tech"]]
    top_boards = sorted(tech_boards or boards_with_score, key=lambda item: item["_score"], reverse=True)[:8]
    weak_boards = sorted(
        [board for board in boards_with_score if board["_score"] < 35 or board["_ret5"] < 0],
        key=lambda item: (item["_score"], item["_ret5"]),
    )[:8]

    for leader in leaders:
        for key in [
            "combined_score",
            "qlib_factor_score",
            "lumen_score",
            "popularity_score",
            "sector_trend_score",
            "ret_5d",
            "ret_20d",
            "rank",
            "rank_change",
        ]:
            leader["_" + key] = as_float(leader.get(key))
        leader["_confluence"] = classify_signal_confluence(leader)
    leaders_sorted = sorted(leaders, key=lambda item: item["_combined_score"], reverse=True)
    confluence = [
        item
        for item in leaders_sorted
        if item["_qlib_factor_score"] >= 60 and item["_lumen_score"] >= 7 and item["_popularity_score"] >= 98
    ][:12]
    divergent = [
        item
        for item in leaders_sorted
        if item["_popularity_score"] >= 98 and (item["_qlib_factor_score"] < 50 or item["_sector_trend_score"] < 45)
    ][:12]
    strong_stock_weak_board = [
        item
        for item in leaders_sorted
        if item["_qlib_factor_score"] >= 75 and item["_sector_trend_score"] < 50
    ][:8]

    history_total = len(history_rows)
    history_ok = sum(1 for row in history_rows if as_float(row.get("rows")) >= 25)
    history_stale = sum(1 for row in history_rows if str(row.get("status", "")).startswith("stale_"))
    history_error = sum(1 for row in history_rows if str(row.get("status", "")).startswith("error"))
    rank_total = int(notes.get("all_code_rows") or 0)
    ranked_rows = int(notes.get("ranked_rows") or 0)
    unranked_rows = int(notes.get("unranked_rows") or 0)
    health_score = 100
    if history_total:
        health_score -= round((history_total - history_ok) / history_total * 35)
    if rank_total:
        health_score -= round(unranked_rows / rank_total * 20)
    health_score -= 5 if history_stale else 0
    health_score = max(0, min(100, health_score))

    mainline = "、".join(short_board(item["board_path"]) for item in top_boards[:3]) or "NA"
    retreat = "、".join(short_board(item["board_path"]) for item in weak_boards[:3]) or "暂无明显退潮板块"
    generated = datetime.now().isoformat(timespec="seconds")

    lines = [
        "# Sector Rotation Daily Analysis",
        "",
        f"Generated: {generated}",
        "",
        "## Executive View",
        f"- 数据健康分: {health_score}/100",
        f"- 当前主线: {mainline}",
        f"- 退潮/弱势: {retreat}",
        f"- 多源共振龙头数量: {len(confluence)}",
        f"- 分歧样本数量: {len(divergent)}",
        "",
        "## Data Health",
        f"- Hot-rank universe: {ranked_rows}/{rank_total} ranked, {unranked_rows} unranked",
        f"- Tech reclassified rows: {reclass_notes.get('tech_rows', 'NA')}/{reclass_notes.get('rows', 'NA')}",
        f"- History coverage: {history_ok}/{history_total}, stale={history_stale}, error={history_error}",
        f"- Unified signals: {len(signal_rows)} rows",
        "",
        "## Board Rotation",
        "| Board | Score | 5D | 20D | Count | Best Rank | Top Stocks |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for board in top_boards:
        lines.append(
            "| "
            + " | ".join(
                [
                    md_cell(board.get("board_path", "")),
                    fmt_num(board.get("sector_trend_score")),
                    fmt_pct(board.get("sector_ret_5d")),
                    fmt_pct(board.get("sector_ret_20d")),
                    str(board.get("stock_count", "")),
                    str(board.get("best_rank", "")),
                    md_cell(board.get("top_stocks", ""), 140),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Confluence Leaders",
            "| Stock | Board | Score | Rank | 5D | 20D | Qlib | Lumen | Hot | Tags |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for stock in (confluence or leaders_sorted[:12]):
        lines.append(
            "| "
            + " | ".join(
                [
                    md_cell(f"{stock.get('name', '')} {stock.get('code', '')}"),
                    md_cell(short_board(stock.get("board_path", ""))),
                    fmt_num(stock.get("combined_score")),
                    str(as_int(stock.get("rank")) or ""),
                    fmt_pct(stock.get("ret_5d")),
                    fmt_pct(stock.get("ret_20d")),
                    fmt_num(stock.get("qlib_factor_score")),
                    fmt_num(stock.get("lumen_score")),
                    fmt_num(stock.get("popularity_score")),
                    md_cell(stock.get("_confluence", "-")),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Divergence Watch",
            "| Stock | Board | Reason | Rank | Qlib | Lumen | Board Score |",
            "|---|---|---|---:|---:|---:|---:|",
        ]
    )
    for stock in divergent[:10]:
        reasons = []
        if stock["_qlib_factor_score"] < 50:
            reasons.append("高人气低qlib")
        if stock["_sector_trend_score"] < 45:
            reasons.append("个股热但板块弱")
        lines.append(
            "| "
            + " | ".join(
                [
                    md_cell(f"{stock.get('name', '')} {stock.get('code', '')}"),
                    md_cell(short_board(stock.get("board_path", ""))),
                    md_cell(",".join(reasons)),
                    str(as_int(stock.get("rank")) or ""),
                    fmt_num(stock.get("qlib_factor_score")),
                    fmt_num(stock.get("lumen_score")),
                    fmt_num(stock.get("sector_trend_score")),
                ]
            )
            + " |"
        )

    if strong_stock_weak_board:
        lines.extend(
            [
                "",
                "## Strong Stock / Weak Board",
                "| Stock | Board | 5D | 20D | Qlib | Board Score |",
                "|---|---|---:|---:|---:|---:|",
            ]
        )
        for stock in strong_stock_weak_board:
            lines.append(
                "| "
                + " | ".join(
                    [
                        md_cell(f"{stock.get('name', '')} {stock.get('code', '')}"),
                        md_cell(short_board(stock.get("board_path", ""))),
                        fmt_pct(stock.get("ret_5d")),
                        fmt_pct(stock.get("ret_20d")),
                        fmt_num(stock.get("qlib_factor_score")),
                        fmt_num(stock.get("sector_trend_score")),
                    ]
                )
                + " |"
            )

    if weak_boards:
        lines.extend(
            [
                "",
                "## Weak Boards",
                "| Board | Score | 5D | 20D | Best Rank |",
                "|---|---:|---:|---:|---:|",
            ]
        )
        for board in weak_boards:
            lines.append(
                "| "
                + " | ".join(
                    [
                        md_cell(board.get("board_path", "")),
                        fmt_num(board.get("sector_trend_score")),
                        fmt_pct(board.get("sector_ret_5d")),
                        fmt_pct(board.get("sector_ret_20d")),
                        str(board.get("best_rank", "")),
                    ]
                )
                + " |"
            )

    lines.extend(
        [
            "",
            "## Risk Notes",
            "- qlib 信号仍是 qlib 表达式兼容公式跑在 AkShare/东财历史行情上，不等同完整 qlib 原生回测。",
            "- 板块 K 线和曲线是热门成分股等权合成，不是官方指数。",
            "- 强势板块若同时出现超买类 LumenAlpha 信号，日报应视为拥挤提示，而不是简单看空。",
            "- 若数据健康分低于 85，应降低日报结论权重，优先修复缺失行情。",
        ]
    )
    if review_text:
        lines.extend(["", "## Pipeline Review Snapshot", "", review_text])

    report_path = REPORT_DIR / f"daily_analysis_{stamp}.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    latest_path = REPORT_DIR / "daily_analysis_latest.md"
    latest_path.write_bytes(report_path.read_bytes())
    WEB_DIR.mkdir(parents=True, exist_ok=True)
    (WEB_DIR / "daily_analysis.md").write_bytes(report_path.read_bytes())
    print(f"Daily analysis: {report_path}")
    return report_path


def main() -> int:
    args = parse_args()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = ROTATION_DIR / "daily_runs" / stamp
    run_dir.mkdir(parents=True, exist_ok=True)

    if args.mode in {"daily", "weekly"}:
        run_step("01_collect_hot_rank", build_collect_cmd(args), run_dir, args.dry_run)
        run_step("02_reclassify_boards", build_reclassify_cmd(args), run_dir, args.dry_run)
    if args.mode in {"daily", "weekly", "pipeline-only"}:
        run_step("03_sector_pipeline", build_pipeline_cmd(args), run_dir, args.dry_run)
    if not args.dry_run:
        generate_analysis_report(stamp)

    summary = {
        "mode": args.mode,
        "stamp": stamp,
        "run_dir": str(run_dir),
        "dry_run": bool(args.dry_run),
    }
    (run_dir / "run_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nDone.")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
