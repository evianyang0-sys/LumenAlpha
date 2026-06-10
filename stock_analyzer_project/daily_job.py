#!/usr/bin/env python3
"""Generate and email the configured daily stock report."""

from __future__ import annotations

import os
from datetime import datetime

from .email_sender import send_html_report
from .reporting import save_daily_report
from .stock_analyzer_main import analyze_stocks


def main() -> int:
    codes = os.getenv("STOCK_REPORT_CODES", "").strip()
    indices = os.getenv("STOCK_REPORT_INDICES", "").strip()
    if not codes and not indices:
        raise RuntimeError("请配置 STOCK_REPORT_CODES 或 STOCK_REPORT_INDICES")

    results = []
    if codes:
        results.extend(analyze_stocks(codes, export_reports=False))
    if indices:
        results.extend(analyze_stocks(indices, is_index=True, export_reports=False))
    if not results:
        raise RuntimeError("所有标的数据获取或分析均失败，未发送空报告")

    report_date = datetime.now().strftime("%Y-%m-%d")
    report_path = save_daily_report(results, report_date)
    smtp_variables = (
        "STOCK_REPORT_EMAIL_TO",
        "STOCK_REPORT_SMTP_HOST",
        "STOCK_REPORT_SMTP_USER",
        "STOCK_REPORT_SMTP_PASSWORD",
    )
    if all(os.getenv(name, "").strip() for name in smtp_variables):
        send_html_report(report_path, f"{report_date} 股票天级分析报告")
        print(f"报告已生成并发送: {report_path}")
    else:
        print(f"报告已生成，SMTP 未完整配置，跳过邮件发送: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
