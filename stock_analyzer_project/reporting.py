#!/usr/bin/env python3
"""HTML report generation for backtests and daily analysis."""

from __future__ import annotations

from datetime import datetime
from html import escape
from pathlib import Path
from typing import Iterable

try:
    from .indicator_engine import INDICATOR_SPECS
except ImportError:
    from indicator_engine import INDICATOR_SPECS


PROJECT_DIR = Path(__file__).resolve().parent
REPORT_ROOT = PROJECT_DIR / "reports"
BACKTEST_REPORT_DIR = REPORT_ROOT / "backtest"
DAILY_REPORT_DIR = REPORT_ROOT / "daily"


def ensure_report_directories() -> None:
    BACKTEST_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    DAILY_REPORT_DIR.mkdir(parents=True, exist_ok=True)


def _number(value, digits=2, suffix="") -> str:
    try:
        return f"{float(value):,.{digits}f}{suffix}"
    except (TypeError, ValueError):
        return "-"


def _safe_filename(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in value)


def _base_styles() -> str:
    return """
    :root{--navy:#0a2458;--navy2:#173b78;--red:#e5484d;--green:#15965b;
      --amber:#d89a23;--ink:#17223b;--muted:#66738f;--line:#dfe5ef;
      --panel:#fff;--bg:#f4f7fb}
    *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
      font-family:"Microsoft YaHei","PingFang SC",Arial,sans-serif}
    .shell{max-width:1480px;margin:auto;padding:24px}.header{display:flex;
      justify-content:space-between;gap:20px;align-items:flex-start;margin-bottom:18px}
    h1{margin:0;color:var(--navy);font-size:28px}.sub{color:var(--muted);
      margin-top:8px;font-size:14px}.badge{display:inline-block;padding:6px 10px;
      border:1px solid var(--line);border-radius:7px;background:#fff;color:var(--navy);
      font-size:13px;margin-left:6px}.grid{display:grid;gap:14px}
    .metrics{grid-template-columns:repeat(4,minmax(0,1fr));margin-bottom:14px}
    .metric,.panel{background:var(--panel);border:1px solid var(--line);
      border-radius:10px;box-shadow:0 2px 10px rgba(20,45,90,.035)}
    .metric{padding:18px}.metric-label{font-size:13px;color:var(--muted);
      font-weight:700}.metric-value{font-size:28px;font-weight:800;margin-top:8px;
      color:var(--navy)}.positive{color:var(--red)}.negative{color:var(--green)}
    .layout{grid-template-columns:minmax(0,1fr) 340px}.panel{padding:18px;
      margin-bottom:14px}.panel h2{font-size:16px;color:var(--navy);margin:0 0 14px}
    .toolbar{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px}
    button{border:1px solid var(--line);background:#fff;color:var(--navy);
      padding:7px 13px;border-radius:6px;cursor:pointer;font-weight:700}
    button.active{background:var(--navy);color:#fff;border-color:var(--navy)}
    table{width:100%;border-collapse:collapse;font-size:13px}
    th{background:#f7f9fc;color:#42506d;text-align:left;position:sticky;top:0}
    th,td{border-bottom:1px solid var(--line);padding:10px 9px;white-space:nowrap}
    tr:hover td{background:#fafcff}.scroll{max-height:600px;overflow:auto}
    .daily-table .signal-cell{white-space:normal;min-width:280px;max-width:440px;
      line-height:1.5;color:#35415c}.daily-table{min-width:1320px}
    .bar-row{display:grid;grid-template-columns:150px 1fr 64px;gap:10px;
      align-items:center;margin:10px 0;font-size:13px}.track{height:11px;background:#edf1f7;
      border-radius:20px;overflow:hidden}.fill{height:100%;background:linear-gradient(90deg,
      var(--navy2),#e85d55);border-radius:20px}.heatmap{display:grid;gap:5px;
      grid-template-columns:120px repeat(5,minmax(54px,1fr));font-size:12px}
    .heatmap>div{padding:9px 6px;border-radius:4px;text-align:center}
    .heat-head{font-weight:700;color:var(--muted)}.heat-name{text-align:left!important;
      font-weight:700}.method{font-size:13px;line-height:1.65;border-bottom:1px solid var(--line);
      padding:0 0 12px;margin:0 0 12px}.method:last-child{border:0;margin:0}
    .method strong{color:var(--navy)}.foot{color:var(--muted);font-size:12px;
      padding:5px 0 20px}.rating{font-weight:800;color:var(--navy)}
    @media(max-width:900px){.metrics,.layout{grid-template-columns:1fr 1fr}
      .layout>aside{grid-column:1/-1}}@media(max-width:620px){
      .shell{padding:12px}.metrics,.layout{grid-template-columns:1fr}.header{display:block}
      .badge{margin:8px 4px 0 0}.heatmap{overflow:auto}.metric-value{font-size:24px}}
    """


def _flatten_backtest(results: dict) -> list[dict]:
    rows = []
    if not results:
        return rows
    if all(isinstance(value, list) for value in results.values()):
        for group, values in results.items():
            for value in values:
                row = dict(value)
                row.setdefault("group", group)
                rows.append(row)
        return rows
    for signal_key, periods in results.items():
        if not isinstance(periods, dict):
            continue
        for period, result in periods.items():
            if not isinstance(result, dict):
                continue
            row = dict(result)
            row.setdefault("signal", signal_key.replace("信号_", ""))
            row.setdefault("period", period)
            rows.append(row)
    return rows


def save_backtest_report(
    results: dict,
    code: str = "",
    name: str = "",
    source: str = "",
    output_path: str | Path | None = None,
) -> Path:
    ensure_report_directories()
    rows = _flatten_backtest(results)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    label = _safe_filename(f"{code}_{name}".strip("_") or "backtest")
    path = Path(output_path) if output_path else BACKTEST_REPORT_DIR / f"{label}_{timestamp}.html"

    active = [row for row in rows if int(row.get("count", 0) or 0) > 0]
    total_samples = sum(int(row.get("count", 0) or 0) for row in active)
    avg_win = sum(float(row.get("win_rate", 0) or 0) for row in active) / len(active) if active else 0
    avg_return = sum(float(row.get("avg_return", 0) or 0) for row in active) / len(active) if active else 0
    best = max(active, key=lambda row: float(row.get("win_rate", 0) or 0), default={})

    sorted_rows = sorted(
        rows,
        key=lambda row: (
            float(row.get("win_rate", 0) or 0),
            int(row.get("count", 0) or 0),
        ),
        reverse=True,
    )
    table_rows = []
    for rank, row in enumerate(sorted_rows, 1):
        ret = float(row.get("avg_return", 0) or 0)
        table_rows.append(
            "<tr data-category='{category}'><td>{rank}</td><td>{signal}</td>"
            "<td>{category}</td><td>{period}</td><td>{count}</td>"
            "<td class='{win_class}'>{win}</td><td class='{ret_class}'>{ret}</td>"
            "<td>{maximum}</td><td>{minimum}</td></tr>".format(
                rank=rank,
                signal=escape(str(row.get("signal", "-"))),
                category=escape(str(row.get("category", row.get("signal_type", "-")))),
                period=escape(str(row.get("period", f"{row.get('days', '-')}日"))),
                count=int(row.get("count", 0) or 0),
                win_class="positive" if float(row.get("win_rate", 0) or 0) >= 50 else "",
                win=_number(row.get("win_rate"), suffix="%"),
                ret_class="positive" if ret > 0 else "negative" if ret < 0 else "",
                ret=_number(ret, suffix="%"),
                maximum=_number(row.get("max_return"), suffix="%"),
                minimum=_number(row.get("min_return"), suffix="%"),
            )
        )

    top_rows = sorted(active, key=lambda row: float(row.get("win_rate", 0) or 0), reverse=True)[:10]
    bars = "".join(
        "<div class='bar-row'><span>{}</span><div class='track'><div class='fill' "
        "style='width:{}%'></div></div><strong>{}</strong></div>".format(
            escape(str(row.get("signal", "-"))),
            max(0, min(100, float(row.get("win_rate", 0) or 0))),
            _number(row.get("win_rate"), 1, "%"),
        )
        for row in top_rows
    ) or "<p class='sub'>暂无有效样本。</p>"

    periods = ["1日", "3日", "5日", "10日", "20日"]
    by_signal = {}
    for row in active:
        by_signal.setdefault(str(row.get("signal", "-")), {})[
            str(row.get("period", f"{row.get('days', '-')}日"))
        ] = float(row.get("win_rate", 0) or 0)
    heat_cells = "".join(f"<div class='heat-head'>{period}</div>" for period in periods)
    heatmap = "<div class='heatmap'><div></div>" + heat_cells
    for signal, values in list(by_signal.items())[:12]:
        heatmap += f"<div class='heat-name'>{escape(signal)}</div>"
        for period in periods:
            value = values.get(period)
            if value is None:
                heatmap += "<div style='background:#f4f6fa;color:#a0a8b8'>-</div>"
            else:
                distance = min(abs(value - 50) / 20, 1)
                color = f"rgba(229,72,77,{0.15 + distance * 0.65})" if value >= 50 else f"rgba(21,150,91,{0.15 + distance * 0.65})"
                heatmap += f"<div style='background:{color}'>{value:.1f}</div>"
    heatmap += "</div>"

    methods = "".join(
        f"<div class='method'><strong>{escape(name)}</strong><br>"
        f"{escape(str(spec['definition']))}<br><span class='sub'>"
        f"{escape(str(spec['source']))}</span></div>"
        for name, spec in INDICATOR_SPECS.items()
    )
    best_label = escape(str(best.get("signal", "暂无")))
    best_value = _number(best.get("win_rate"), 1, "%") if best else "-"
    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    html = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>{escape(name or code)} LumenAlpha 回测报告</title><style>{_base_styles()}</style></head>
    <body><main class="shell"><header class="header"><div><h1>LumenAlpha 回测报告</h1>
    <div class="sub">{escape(name)} {escape(code)} · 生成于 {generated}</div></div>
    <div><span class="badge">数据源 {escape(source or "-")}</span>
    <span class="badge">不含交易成本</span></div></header>
    <section class="grid metrics"><div class="metric"><div class="metric-label">累计样本</div>
    <div class="metric-value">{total_samples:,}</div></div><div class="metric">
    <div class="metric-label">平均胜率</div><div class="metric-value positive">{avg_win:.2f}%</div>
    </div><div class="metric"><div class="metric-label">平均持有期收益</div>
    <div class="metric-value {'positive' if avg_return >= 0 else 'negative'}">{avg_return:+.2f}%</div>
    </div><div class="metric"><div class="metric-label">最高胜率信号</div>
    <div class="metric-value" style="font-size:21px">{best_label} {best_value}</div></div></section>
    <div class="grid layout"><section><div class="panel"><h2>信号胜率 TOP 10</h2>{bars}</div>
    <div class="panel"><h2>持有周期胜率热力图</h2>{heatmap}</div>
    <div class="panel"><h2>回测结果明细</h2><div class="toolbar">
    <button class="active" data-filter="all">全部</button><button data-filter="短线">短线</button>
    <button data-filter="长线">长线</button></div><div class="scroll"><table><thead><tr>
    <th>排名</th><th>信号</th><th>类别</th><th>持有期</th><th>样本</th>
    <th>胜率</th><th>平均收益</th><th>最大收益</th><th>最小收益</th></tr></thead>
    <tbody>{''.join(table_rows)}</tbody></table></div></div></section>
    <aside><div class="panel"><h2>方法说明与指标定义</h2>{methods}</div>
    <div class="panel"><h2>风险提示</h2><p class="method">历史回测不代表未来表现。
    当前结果按信号触发后固定交易日计算，未模拟资金占用、重复持仓、手续费、滑点、
    涨跌停与停牌约束，因此不能当作完整策略净值。</p></div></aside></div>
    <div class="foot">指标计算统一由 indicator_engine.py 提供。</div></main>
    <script>document.querySelectorAll('button[data-filter]').forEach(btn=>btn.onclick=()=>{{
    document.querySelectorAll('button[data-filter]').forEach(x=>x.classList.remove('active'));
    btn.classList.add('active');const f=btn.dataset.filter;
    document.querySelectorAll('tbody tr').forEach(row=>row.style.display=
    f==='all'||row.dataset.category===f?'':'none');}});</script></body></html>"""
    path.write_text(html, encoding="utf-8")
    return path


def _daily_rows(results: Iterable[dict]) -> str:
    rows = []
    for item in results:
        change = float(item.get("涨跌", 0) or 0)
        structured_signals = item.get("signals") or []
        if structured_signals:
            ranked_signals = sorted(
                structured_signals,
                key=lambda signal: abs(float(signal.get("score", 0) or 0)),
                reverse=True,
            )
            names = [str(signal.get("name", "-")) for signal in ranked_signals]
            signal_summary = ", ".join(names[:5])
            if len(names) > 5:
                signal_summary += f" 等{len(names)}项"
            signal_detail = ", ".join(names)
        else:
            signal_summary = str(item.get("信号", "无"))
            signal_detail = signal_summary
        rows.append(
            "<tr><td>{code}</td><td>{name}</td><td>{sector}</td><td>{date}</td>"
            "<td>{close}</td><td class='{change_class}'>{change}</td>"
            "<td>{ma5}</td><td>{rsi}</td><td>{macd}</td><td>{score}</td>"
            "<td class='rating'>{rating}</td><td class='signal-cell' title='{signal_detail}'>"
            "{signals}</td><td>{source}</td></tr>".format(
                code=escape(str(item.get("代码", "-"))),
                name=escape(str(item.get("名称", "-"))),
                sector=escape(str(item.get("板块", "-") or "-")),
                date=escape(str(item.get("日期", "-"))),
                close=_number(item.get("收盘")),
                change_class="positive" if change > 0 else "negative" if change < 0 else "",
                change=f"{change:+.2f}",
                ma5=_number(item.get("MA5")),
                rsi=_number(item.get("RSI"), 1),
                macd=_number(item.get("MACD"), 3),
                score=_number(item.get("得分"), 1),
                rating=escape(str(item.get("评级", "-"))),
                signals=escape(signal_summary),
                signal_detail=escape(signal_detail, quote=True),
                source=escape(str(item.get("数据源", "-"))),
            )
        )
    return "".join(rows)


def render_daily_report_html(results: list[dict], report_date: str | None = None) -> str:
    report_date = report_date or datetime.now().strftime("%Y-%m-%d")
    sorted_results = sorted(results, key=lambda item: float(item.get("得分", 0) or 0), reverse=True)
    avg_score = (
        sum(float(item.get("得分", 0) or 0) for item in sorted_results) / len(sorted_results)
        if sorted_results else 0
    )
    bullish = sum(1 for item in sorted_results if float(item.get("涨跌", 0) or 0) > 0)
    top = sorted_results[0] if sorted_results else {}
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>{report_date} LumenAlpha 天级报告</title><style>{_base_styles()}</style></head>
    <body><main class="shell"><header class="header"><div><h1>LumenAlpha 天级报告</h1>
    <div class="sub">{report_date} · 日线收盘数据</div></div>
    <span class="badge">每日 20:00</span></header><section class="grid metrics">
    <div class="metric"><div class="metric-label">分析标的</div>
    <div class="metric-value">{len(sorted_results)}</div></div>
    <div class="metric"><div class="metric-label">上涨标的</div>
    <div class="metric-value positive">{bullish}</div></div>
    <div class="metric"><div class="metric-label">平均评分</div>
    <div class="metric-value">{avg_score:.1f}</div></div>
    <div class="metric"><div class="metric-label">最高评分</div>
    <div class="metric-value" style="font-size:21px">{escape(str(top.get('名称', '暂无')))}
    {_number(top.get('得分'), 1)}</div></div></section>
    <section class="panel"><h2>当日汇总</h2><div class="scroll"><table class="daily-table"><thead><tr>
    <th>代码</th><th>名称</th><th>板块</th><th>日期</th><th>收盘</th><th>涨跌</th>
    <th>MA5</th><th>RSI</th><th>MACD</th><th>信号权重分</th><th>评级</th><th>信号摘要</th>
    <th>数据源</th></tr></thead>
    <tbody>{_daily_rows(sorted_results)}</tbody></table></div></section>
    <section class="panel"><h2>口径说明</h2><p class="method">报告使用日 K 数据。
    VWAP 为所提供日线序列上的累计典型价格成交量加权代理，不等同于交易所逐笔或分钟级
    当日 VWAP。BBD 为项目自定义 AO 动量派生项，不代表真实主力资金流。
    信号权重分会叠加相关指标与共振信号，仅用于排序，不应直接解释为概率或收益预测。</p></section>
    <div class="foot">本报告仅用于量化研究，不构成投资建议。</div></main></body></html>"""


def save_daily_report(
    results: list[dict],
    report_date: str | None = None,
    output_path: str | Path | None = None,
) -> Path:
    ensure_report_directories()
    report_date = report_date or datetime.now().strftime("%Y-%m-%d")
    timestamp = datetime.now().strftime("%H%M%S")
    path = Path(output_path) if output_path else DAILY_REPORT_DIR / f"daily_{report_date}_{timestamp}.html"
    path.write_text(render_daily_report_html(results, report_date), encoding="utf-8")
    return path
