#!/usr/bin/env python3
"""SMTP delivery for generated daily reports."""

from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from pathlib import Path


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"缺少环境变量 {name}")
    return value


def send_html_report(report_path: str | Path, subject: str) -> None:
    path = Path(report_path)
    recipients = [
        value.strip()
        for value in _required_env("STOCK_REPORT_EMAIL_TO").split(",")
        if value.strip()
    ]
    host = _required_env("STOCK_REPORT_SMTP_HOST")
    user = _required_env("STOCK_REPORT_SMTP_USER")
    password = _required_env("STOCK_REPORT_SMTP_PASSWORD")
    port = int(os.getenv("STOCK_REPORT_SMTP_PORT", "465"))
    use_ssl = os.getenv("STOCK_REPORT_SMTP_SSL", "true").lower() in {
        "1",
        "true",
        "yes",
    }

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = os.getenv("STOCK_REPORT_EMAIL_FROM", user)
    message["To"] = ", ".join(recipients)
    html = path.read_text(encoding="utf-8")
    message.set_content("请使用支持 HTML 的邮件客户端查看股票天级报告。")
    message.add_alternative(html, subtype="html")
    message.add_attachment(
        html.encode("utf-8"),
        maintype="text",
        subtype="html",
        filename=path.name,
    )

    if use_ssl:
        with smtplib.SMTP_SSL(host, port, timeout=30) as smtp:
            smtp.login(user, password)
            smtp.send_message(message)
    else:
        with smtplib.SMTP(host, port, timeout=30) as smtp:
            smtp.starttls()
            smtp.login(user, password)
            smtp.send_message(message)
