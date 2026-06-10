#!/usr/bin/env python3
"""Industry-aware qualitative research report for the configured stock pool."""

from __future__ import annotations

from datetime import datetime
from html import escape
from pathlib import Path

import numpy as np
import pandas as pd

from .reporting import DAILY_REPORT_DIR, ensure_report_directories


SECTOR_PROFILES = {
    "储存芯片": {
        "context": "行业同时受存储价格周期、AI服务器与端侧设备需求、库存变化和国产替代影响，盈利弹性通常高于收入弹性。",
        "risk": "价格回落、库存重新累积、下游需求不及预期及高研发投入。",
    },
    "液冷": {
        "context": "算力密度提升推动液冷渗透，但股价最终需要由客户认证、项目交付和订单收入兑现支撑。",
        "risk": "主题交易先于业绩、项目节奏延后、竞争加剧和估值消化。",
    },
    "消费电子": {
        "context": "行业取决于终端需求复苏、AI终端创新、客户新品周期和供应链份额变化。",
        "risk": "大客户集中、消费需求波动、产品降价和资本开支回报不足。",
    },
    "PCB": {
        "context": "AI服务器、高速交换与高端通信推动高层数和高频高速PCB需求，产品结构升级比单纯产量增长更重要。",
        "risk": "扩产兑现不及预期、原材料涨价、客户集中和高景气预期透支。",
    },
    "光模块": {
        "context": "行业核心变量是海外云厂商资本开支、速率升级和高速光模块出货，景气高但估值与预期也通常较高。",
        "risk": "客户资本开支放缓、技术迭代、海外贸易限制和高位估值回撤。",
    },
    "食品消费": {
        "context": "消费板块更重视需求韧性、渠道效率和成本变化；其中乳品零售与生猪养殖的周期驱动并不相同。",
        "risk": "终端需求偏弱、原料或养殖成本波动、食品安全和渠道扩张效率。",
    },
    "传媒": {
        "context": "数字营销和内容行业受广告预算、平台流量、AI内容工具与监管环境共同影响，主题弹性通常较高。",
        "risk": "客户预算收缩、回款与商誉压力、平台政策变化和题材交易退潮。",
    },
    "商业航天": {
        "context": "商业航天与高端材料具备长期政策和产业趋势，但订单、产能与利润兑现节奏往往慢于主题交易。",
        "risk": "项目延期、订单不连续、资本开支较大和概念映射强于实际收入贡献。",
    },
    "机器人": {
        "context": "机器人板块关注核心零部件、自动化集成和量产进度，真正的竞争力来自客户验证与规模化降本。",
        "risk": "量产不及预期、主题估值过高、技术路线变化及传统业务拖累。",
    },
    "新能源电池": {
        "context": "行业需求仍由新能源汽车、储能和设备更新驱动，但盈利取决于产品结构、海外进展与供需格局。",
        "risk": "价格竞争、产能过剩、海外政策、客户议价和新技术替代。",
    },
    "证券": {
        "context": "证券与期货平台对市场成交、风险偏好和资本市场政策高度敏感，具有明显市场贝塔。",
        "risk": "成交回落、权益市场调整、业务监管变化和高弹性后的估值回撤。",
    },
    "光伏": {
        "context": "终端装机需求长期存在，但制造环节更关键的变量是供给出清、产品价格和现金流修复。",
        "risk": "产能过剩、价格战、减值压力、海外贸易壁垒和融资需求。",
    },
    "算力": {
        "context": "算力服务受AI需求、IDC资源、电力成本和客户上架率驱动，收入增长必须与现金流和资本开支效率匹配。",
        "risk": "重资产扩张、上架率不足、应收账款、能源成本和行业价格竞争。",
    },
}


COMPANY_ROLES = {
    "301308": "存储产品与解决方案企业，对存储价格周期和库存变化较敏感。",
    "603986": "存储与MCU等芯片平台，兼具行业周期与国产替代属性。",
    "000021": "电子制造与存储相关业务并存，更需要观察订单结构和盈利质量。",
    "002837": "机房与数据中心温控企业，算力基础设施景气是重要驱动。",
    "300153": "备用电源与能源保障设备企业，在本股票池中按数据中心基础设施方向观察。",
    "601138": "大型电子制造平台，受AI服务器、通信设备及大客户订单周期影响。",
    "301413": "传感器企业，关注消费电子与汽车等应用放量。",
    "605488": "功能性材料企业，关注电子材料应用拓展及新产能兑现。",
    "300476": "高端PCB企业，受益于AI服务器和高速通信产品升级。",
    "002463": "通信与服务器PCB企业，业绩弹性与高端产品占比密切相关。",
    "300308": "高速光模块龙头之一，海外AI资本开支是关键景气变量。",
    "300394": "光器件平台企业，关注高速率产品放量与产品结构提升。",
    "300502": "高速光模块企业，景气弹性高，同时对海外客户资本开支敏感。",
    "605179": "乳品与门店零售企业，核心是同店、门店扩张和供应链效率。",
    "002714": "生猪养殖企业，判断重点是猪价、养殖成本和资产负债表。",
    "300058": "数字营销企业，受客户广告预算、出海营销和AI工具应用影响。",
    "600986": "互联网营销企业，关注业务质量、回款和新业务兑现。",
    "002342": "索具与工程装备企业，商业航天更多体现主题与潜在应用映射。",
    "002149": "稀有金属材料企业，航空航天用材需求和原料价格均重要。",
    "300915": "汽车环保与零部件企业，在机器人主题下需要特别核实实际业务贡献。",
    "603667": "精密轴承企业，人形机器人零部件预期与传统业务共同影响估值。",
    "002009": "智能装备与循环产业企业，关注自动化订单和资产运营效率。",
    "300450": "锂电智能装备企业，订单与验收节奏通常领先或滞后于电池扩产周期。",
    "300750": "动力与储能电池龙头，产品、客户、海外布局和产业链议价能力更关键。",
    "002961": "期货及衍生品服务企业，业绩与市场活跃度、风险管理业务相关。",
    "300803": "金融信息服务平台，受市场成交和投资者活跃度驱动。",
    "600030": "综合证券龙头，业务更均衡，但仍具明显资本市场贝塔。",
    "002865": "光伏电池企业，重点观察产品价格、产能利用率与现金流。",
    "002506": "光伏组件及系统企业，关注订单质量、毛利和资产负债压力。",
    "300846": "云计算与IDC服务企业，关注资源上架率和资本开支回报。",
    "002015": "能源服务企业，算力相关布局需与传统能源业务和实际项目进度结合判断。",
}


HIGH_BETA_SECTORS = {"液冷", "PCB", "光模块", "传媒", "商业航天", "机器人", "光伏", "算力"}


def _value(series: pd.Series, fallback=np.nan) -> float:
    try:
        return float(series)
    except (TypeError, ValueError):
        return fallback


def _pct(value: float, digits=1) -> str:
    return "-" if pd.isna(value) else f"{value:+.{digits}f}%"


def _num(value: float, digits=2) -> str:
    return "-" if pd.isna(value) else f"{value:,.{digits}f}"


def _stock_analysis(item: dict) -> dict:
    frame = item["df"]
    current = frame.iloc[-1]
    previous = frame.iloc[-2]
    close = _value(current["收盘"])
    previous_close = _value(previous["收盘"])
    ma5 = _value(current.get("MA5"))
    ma20 = _value(current.get("MA20"))
    ma50 = _value(current.get("MA50"))
    ema200 = _value(current.get("EMA200"))
    rsi = _value(current.get("RSI"))
    macd = _value(current.get("MACD"))
    atr = _value(current.get("ATR"))
    volume = _value(current.get("成交量"))
    volume_ma20 = _value(current.get("VOL_MA20"))
    ret1 = (close / previous_close - 1) * 100 if previous_close else np.nan
    ret20 = (close / _value(frame["收盘"].iloc[-21]) - 1) * 100 if len(frame) > 20 else np.nan
    ret60 = (close / _value(frame["收盘"].iloc[-61]) - 1) * 100 if len(frame) > 60 else np.nan
    volume_ratio = volume / volume_ma20 if volume_ma20 and not pd.isna(volume_ma20) else np.nan
    atr_pct = atr / close * 100 if close and not pd.isna(atr) else np.nan
    distance_ma20 = (close / ma20 - 1) * 100 if ma20 and not pd.isna(ma20) else np.nan
    distance_ema200 = (close / ema200 - 1) * 100 if ema200 and not pd.isna(ema200) else np.nan
    high20 = _value(frame["最高"].tail(20).max())
    low20 = _value(frame["最低"].tail(20).min())
    drawdown20 = (close / high20 - 1) * 100 if high20 else np.nan
    rebound20 = (close / low20 - 1) * 100 if low20 else np.nan

    medium_up = close > ma20 > ma50 if not any(pd.isna(v) for v in (ma20, ma50)) else False
    medium_down = close < ma20 < ma50 if not any(pd.isna(v) for v in (ma20, ma50)) else False
    long_up = close > ema200 if not pd.isna(ema200) else False
    momentum_up = macd > 0 if not pd.isna(macd) else False
    overbought = rsi >= 70 if not pd.isna(rsi) else False
    oversold = rsi < 30 if not pd.isna(rsi) else False
    near_high = drawdown20 > -5 if not pd.isna(drawdown20) else False
    volume_expanded = volume_ratio >= 1.35 if not pd.isna(volume_ratio) else False

    evidence = []
    risks = []
    if medium_up:
        evidence.append("收盘价位于MA20和MA50上方，中期结构偏多")
    elif medium_down:
        risks.append("价格、MA20与MA50呈弱势排列")
    elif close > ma20:
        evidence.append("价格已站上MA20，但中期均线尚未完全转强")
    else:
        risks.append("价格仍在MA20下方，修复尚未确认")
    if long_up:
        evidence.append("价格处于EMA200上方，长期趋势基础尚在")
    else:
        risks.append("价格位于EMA200下方，长期趋势约束仍在")
    if momentum_up:
        evidence.append("MACD柱线为正，短期动量改善")
    else:
        risks.append("MACD柱线为负，短期动量仍偏弱")
    if volume_expanded:
        evidence.append(f"成交量约为20日均量的{volume_ratio:.1f}倍，资金参与度上升")
    elif not pd.isna(volume_ratio) and volume_ratio < 0.75:
        risks.append("成交量明显低于20日均量，趋势确认度有限")
    if overbought:
        risks.append(f"RSI为{rsi:.1f}，短线已偏热")
    elif oversold:
        evidence.append(f"RSI为{rsi:.1f}，具备超跌修复条件")
        risks.append("超卖本身不代表趋势已经反转")

    if medium_up and long_up and momentum_up:
        if overbought or (near_high and ret20 > 15):
            state = "强势但不宜追高"
            stance = "趋势占优，等待回踩确认"
        else:
            state = "趋势延续"
            stance = "偏强跟踪"
    elif close > ma20 and momentum_up:
        state = "修复转强"
        stance = "等待中期均线确认"
    elif oversold and medium_down:
        state = "超跌观察"
        stance = "仅适合观察反弹确认"
    elif medium_down:
        state = "弱势下行"
        stance = "风险优先"
    else:
        state = "区间震荡"
        stance = "等待方向选择"

    sector = item.get("板块", "")
    if sector in HIGH_BETA_SECTORS and state in {"超跌观察", "弱势下行", "区间震荡"}:
        risks.append("所属板块交易弹性较高，弱势阶段容易放大回撤")

    support = ma20 if close >= ma20 and not pd.isna(ma20) else low20
    confirmation = (
        f"后续若能放量站稳MA20（{ma20:.2f}）并推动MACD翻红，修复可信度会提高"
        if close < ma20 and not pd.isna(ma20)
        else f"重点观察MA20（{ma20:.2f}）能否继续提供支撑"
    )
    invalidation = (
        f"若有效跌破近20日低点或参考支撑{support:.2f}，当前判断需要转弱"
        if not pd.isna(support)
        else "若价格重新跌破近期整理区间，当前判断需要转弱"
    )

    signals = item.get("signals") or []
    ranked_signals = sorted(
        signals,
        key=lambda signal: abs(float(signal.get("score", 0) or 0)),
        reverse=True,
    )
    signal_names = [str(signal.get("name", "-")) for signal in ranked_signals[:4]]
    signal_text = "、".join(signal_names) if signal_names else "暂无明显辅助信号"

    profile = SECTOR_PROFILES.get(sector, {"context": "行业景气与公司自身经营共同决定中期表现。", "risk": "行业需求和公司执行风险。"})
    role = COMPANY_ROLES.get(item["代码"], f"本报告按{sector}板块进行观察。")
    sector_lens = (
        "考虑到该板块交易弹性较高"
        if sector in HIGH_BETA_SECTORS
        else "结合行业驱动、公司定位与当前价格位置"
    )
    conclusion = (
        f"{item['名称']}在{sector}板块中的观察重点是：{role}"
        f"当前技术状态属于“{state}”。{sector_lens}，综合判断为“{stance}”。"
        f"量化信号只作为辅助，目前较突出的信号为{signal_text}。"
    )

    return {
        **item,
        "role": role,
        "sector_context": profile["context"],
        "sector_risk": profile["risk"],
        "state": state,
        "stance": stance,
        "conclusion": conclusion,
        "evidence": evidence[:4] or ["当前缺少足够强的趋势确认信号"],
        "risks": risks[:5] or ["短线波动仍可能造成结论反复"],
        "confirmation": confirmation,
        "invalidation": invalidation,
        "metrics": {
            "收盘": close,
            "日涨跌": ret1,
            "20日收益": ret20,
            "60日收益": ret60,
            "MA5": ma5,
            "MA20": ma20,
            "距MA20": distance_ma20,
            "距EMA200": distance_ema200,
            "RSI": rsi,
            "MACD": macd,
            "量比": volume_ratio,
            "ATR占比": atr_pct,
            "距20日高点": drawdown20,
            "距20日低点": rebound20,
        },
    }


def _metric(label: str, value: str) -> str:
    return f"<div class='metric'><span>{escape(label)}</span><strong>{escape(value)}</strong></div>"


def _stock_card(stock: dict) -> str:
    metrics = stock["metrics"]
    metric_html = "".join(
        [
            _metric("收盘", _num(metrics["收盘"])),
            _metric("日涨跌", _pct(metrics["日涨跌"])),
            _metric("20日收益", _pct(metrics["20日收益"])),
            _metric("60日收益", _pct(metrics["60日收益"])),
            _metric("距MA20", _pct(metrics["距MA20"])),
            _metric("距EMA200", _pct(metrics["距EMA200"])),
            _metric("RSI", _num(metrics["RSI"], 1)),
            _metric("MACD柱", _num(metrics["MACD"], 3)),
            _metric("量比(20日)", _num(metrics["量比"], 2)),
            _metric("ATR/价格", _pct(metrics["ATR占比"])),
        ]
    )
    evidence = "".join(f"<li>{escape(text)}</li>" for text in stock["evidence"])
    risks = "".join(f"<li>{escape(text)}</li>" for text in stock["risks"])
    state_class = {
        "趋势延续": "good",
        "修复转强": "good",
        "强势但不宜追高": "warn",
        "超跌观察": "warn",
        "弱势下行": "bad",
        "区间震荡": "neutral",
    }.get(stock["state"], "neutral")
    return f"""
    <article class="stock-card">
      <div class="stock-head">
        <div><h3>{escape(stock['名称'])} <small>{escape(stock['代码'])}</small></h3>
        <p>{escape(stock['role'])}</p></div>
        <div class="state {state_class}">{escape(stock['state'])}</div>
      </div>
      <div class="metrics">{metric_html}</div>
      <div class="judgment"><b>综合判断：</b>{escape(stock['conclusion'])}</div>
      <div class="evidence-grid">
        <div><h4>支持因素</h4><ul>{evidence}</ul></div>
        <div><h4>反证与风险</h4><ul>{risks}</ul></div>
      </div>
      <div class="conditions"><b>观察条件：</b>{escape(stock['confirmation'])}。<br>
      <b>判断失效：</b>{escape(stock['invalidation'])}。</div>
    </article>"""


def render_research_report(results: list[dict], report_date: str | None = None) -> str:
    report_date = report_date or datetime.now().strftime("%Y-%m-%d")
    analyzed = [_stock_analysis(item) for item in results]
    sectors = []
    for item in analyzed:
        if item["板块"] not in sectors:
            sectors.append(item["板块"])
    counts = {}
    for item in analyzed:
        counts[item["state"]] = counts.get(item["state"], 0) + 1

    navigation = "".join(
        f"<a href='#{escape(sector)}'>{escape(sector)}</a>" for sector in sectors
    )
    sections = []
    for sector in sectors:
        stocks = [item for item in analyzed if item["板块"] == sector]
        profile = SECTOR_PROFILES.get(sector, {})
        cards = "".join(_stock_card(stock) for stock in stocks)
        sections.append(
            f"""<section class="sector" id="{escape(sector)}"><div class="sector-head">
            <div><h2>{escape(sector)}</h2><p>{escape(profile.get('context', ''))}</p></div>
            <span>{len(stocks)}只</span></div>
            <div class="sector-risk"><b>行业主要风险：</b>{escape(profile.get('risk', ''))}</div>
            {cards}</section>"""
        )

    latest_date = max(str(item.get("日期", "")) for item in analyzed)
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>{report_date} LumenAlpha 行业研究报告</title><style>
    :root{{--navy:#0b285d;--ink:#17213a;--muted:#64718d;--line:#dce3ee;
      --bg:#f4f7fb;--red:#d9434e;--green:#148454;--amber:#b87808}}
    *{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;background:var(--bg);
      color:var(--ink);font-family:"Microsoft YaHei","PingFang SC",Arial,sans-serif}}
    .shell{{max-width:1500px;margin:auto;padding:24px}}header{{background:linear-gradient(120deg,#071d47,#123f82);
      color:white;border-radius:14px;padding:28px 32px}}h1{{margin:0;font-size:30px}}
    header p{{margin:10px 0 0;color:#d7e4ff}}.overview{{display:grid;
      grid-template-columns:repeat(5,1fr);gap:12px;margin:16px 0}}.summary{{background:white;
      border:1px solid var(--line);border-radius:10px;padding:16px}}.summary span{{display:block;
      color:var(--muted);font-size:13px}}.summary strong{{display:block;margin-top:7px;
      color:var(--navy);font-size:25px}}nav{{display:flex;gap:8px;flex-wrap:wrap;
      background:white;border:1px solid var(--line);border-radius:10px;padding:12px;margin-bottom:16px}}
    nav a{{text-decoration:none;color:var(--navy);border:1px solid var(--line);
      border-radius:20px;padding:6px 11px;font-size:13px}}.methodology,.sector{{background:white;
      border:1px solid var(--line);border-radius:12px;padding:20px;margin-bottom:16px}}
    .methodology h2,.sector h2{{margin:0;color:var(--navy)}}.methodology p,.sector-head p{{
      color:var(--muted);line-height:1.7;margin:8px 0 0}}.sector-head{{display:flex;
      justify-content:space-between;gap:24px;align-items:flex-start}}.sector-head span{{
      color:var(--navy);font-weight:700;background:#eef3fb;padding:7px 11px;border-radius:8px}}
    .sector-risk{{margin:13px 0 16px;padding:11px 13px;background:#fff8ea;color:#74500d;
      border-left:3px solid #d79b31;border-radius:4px;font-size:13px}}.stock-card{{
      border:1px solid var(--line);border-radius:10px;padding:18px;margin-top:13px;
      box-shadow:0 2px 9px rgba(20,44,90,.035)}}.stock-head{{display:flex;
      justify-content:space-between;gap:18px}}h3{{margin:0;color:var(--navy);font-size:19px}}
    h3 small{{font-size:13px;color:var(--muted);margin-left:5px}}.stock-head p{{margin:7px 0 0;
      color:var(--muted);font-size:13px}}.state{{height:max-content;padding:7px 11px;
      border-radius:7px;font-weight:700;font-size:13px;white-space:nowrap}}.state.good{{
      color:var(--red);background:#fff0f1}}.state.warn{{color:var(--amber);background:#fff7e7}}
    .state.bad{{color:var(--green);background:#eaf8f1}}.state.neutral{{color:#516079;
      background:#eef2f7}}.metrics{{display:grid;grid-template-columns:repeat(10,minmax(78px,1fr));
      gap:7px;margin:15px 0}}.metric{{background:#f7f9fc;border-radius:6px;padding:9px}}
    .metric span{{display:block;color:var(--muted);font-size:11px}}.metric strong{{display:block;
      margin-top:4px;font-size:13px}}.judgment{{line-height:1.75;padding:12px 14px;
      border-radius:7px;background:#f2f6fc;font-size:14px}}.evidence-grid{{display:grid;
      grid-template-columns:1fr 1fr;gap:12px;margin-top:12px}}.evidence-grid>div{{border:1px solid
      var(--line);border-radius:7px;padding:12px 14px}}h4{{margin:0 0 7px;color:var(--navy);
      font-size:14px}}ul{{margin:0;padding-left:19px;color:#46536d;font-size:13px;line-height:1.65}}
    .conditions{{margin-top:12px;color:#46536d;line-height:1.7;font-size:13px}}footer{{
      color:var(--muted);font-size:12px;line-height:1.7;padding:4px 4px 28px}}
    @media(max-width:1000px){{.overview{{grid-template-columns:repeat(2,1fr)}}
      .metrics{{grid-template-columns:repeat(5,1fr)}}}}
    @media(max-width:650px){{.shell{{padding:10px}}header{{padding:22px 18px}}
      .overview,.evidence-grid{{grid-template-columns:1fr}}.metrics{{grid-template-columns:repeat(2,1fr)}}
      .stock-head,.sector-head{{display:block}}.state{{display:inline-block;margin-top:10px}}}}
    </style></head><body><main class="shell"><header><h1>LumenAlpha 行业研究报告</h1>
    <p>生成日期 {escape(report_date)} · 行情数据截至 {escape(latest_date)} · 共 {len(analyzed)} 只股票</p>
    </header><div class="overview">
    <div class="summary"><span>股票数量</span><strong>{len(analyzed)}</strong></div>
    <div class="summary"><span>趋势延续</span><strong>{counts.get('趋势延续', 0)}</strong></div>
    <div class="summary"><span>修复转强</span><strong>{counts.get('修复转强', 0)}</strong></div>
    <div class="summary"><span>超跌/弱势</span><strong>{counts.get('超跌观察', 0) + counts.get('弱势下行', 0)}</strong></div>
    <div class="summary"><span>区间及高位观察</span><strong>{counts.get('区间震荡', 0) + counts.get('强势但不宜追高', 0)}</strong></div>
    </div><nav>{navigation}</nav><section class="methodology"><h2>如何阅读本报告</h2>
    <p>综合判断由行业属性、公司在产业链中的位置、价格相对MA20/MA50/EMA200的位置、
    MACD与RSI动量、20/60日表现、量能和波动率共同形成。Python脚本触发的信号只作为辅助证据，
    不再直接用累计分数决定结论。报告重点是说明当前状态、支持证据、反证以及什么条件会改变判断。</p>
    </section>{''.join(sections)}<footer>行业内容采用结构性分析框架，不替代公司公告和财务尽调。
    技术分析可能失效，历史行情不代表未来表现。本报告仅用于研究，不构成投资建议。</footer>
    </main></body></html>"""


def save_research_report(
    results: list[dict],
    report_date: str | None = None,
    output_path: str | Path | None = None,
) -> Path:
    ensure_report_directories()
    report_date = report_date or datetime.now().strftime("%Y-%m-%d")
    timestamp = datetime.now().strftime("%H%M%S")
    path = (
        Path(output_path)
        if output_path
        else DAILY_REPORT_DIR / f"research_{report_date}_{timestamp}.html"
    )
    path.write_text(render_research_report(results, report_date), encoding="utf-8")
    return path
