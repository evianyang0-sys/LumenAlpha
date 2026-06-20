#!/usr/bin/env python3
"""Generate a catalog of qlib and LumenAlpha factors/signals for the dashboard."""

from __future__ import annotations

import ast
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
QLIB_PATH = ROOT / "microsoft-qlib"
LUMEN_PATH = ROOT / "LumenAlpha" / "stock_analyzer_project"
OUTPUT_DIR = ROOT / "data" / "sector_rotation"
WEB_OUTPUT = ROOT / "web" / "sector_rotation_dashboard" / "factor_catalog.js"

for path in (QLIB_PATH, LUMEN_PATH):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


QLIB_ALPHA158_MEANINGS = {
    "KMID": ("K线实体收益", "($close-$open)/$open，收盘相对开盘的实体强弱。"),
    "KLEN": ("K线振幅", "($high-$low)/$open，日内高低波动幅度。"),
    "KMID2": ("实体占振幅", "($close-$open)/($high-$low)，实体在全日振幅中的占比。"),
    "KUP": ("上影线收益", "高点到实体上沿的距离，相对开盘归一。"),
    "KUP2": ("上影线占振幅", "上影线在全日振幅中的占比。"),
    "KLOW": ("下影线收益", "实体下沿到低点的距离，相对开盘归一。"),
    "KLOW2": ("下影线占振幅", "下影线在全日振幅中的占比。"),
    "KSFT": ("K线偏移", "2*close-high-low，相对开盘归一，衡量收盘在高低区间中的偏向。"),
    "KSFT2": ("K线偏移占振幅", "收盘区间偏向相对全日振幅归一。"),
    "OPEN": ("开盘价归一", "Ref($open,N)/$close，N日前开盘价相对当前收盘价。"),
    "HIGH": ("最高价归一", "Ref($high,N)/$close，N日前最高价相对当前收盘价。"),
    "LOW": ("最低价归一", "Ref($low,N)/$close，N日前最低价相对当前收盘价。"),
    "CLOSE": ("收盘价归一", "Ref($close,N)/$close，N日前收盘价相对当前收盘价。"),
    "VWAP": ("均价归一", "Ref($vwap,N)/$close，N日前成交均价相对当前收盘价。"),
    "VOLUME": ("成交量归一", "Ref($volume,N)/$volume，N日前成交量相对当前成交量。"),
    "ROC": ("价格变化率", "Ref($close,N)/$close，N日前收盘价相对当前收盘价。"),
    "MA": ("均线偏离", "Mean($close,N)/$close，N日均价相对当前收盘价。"),
    "STD": ("价格波动率", "Std($close,N)/$close，N日收盘价标准差相对当前收盘价。"),
    "BETA": ("线性趋势斜率", "Slope($close,N)/$close，N日线性回归斜率归一。"),
    "RSQR": ("趋势线性度", "Rsquare($close,N)，N日线性回归 R 方。"),
    "RESI": ("趋势残差", "Resi($close,N)/$close，N日线性回归残差归一。"),
    "MAX": ("区间高点", "Max($high,N)/$close，N日最高价相对当前收盘价。"),
    "MIN": ("区间低点", "Min($low,N)/$close，N日最低价相对当前收盘价。"),
    "QTLU": ("上分位价格", "Quantile($close,N,0.8)/$close，N日80%分位价。"),
    "QTLD": ("下分位价格", "Quantile($close,N,0.2)/$close，N日20%分位价。"),
    "RANK": ("区间价格位置", "Rank($close,N)，当前收盘价在 N 日窗口内的百分位。"),
    "RSV": ("高低区间位置", "(close-Min(low,N))/(Max(high,N)-Min(low,N))。"),
    "IMAX": ("距前高位置", "IdxMax($high,N)/N，N日最高价距当前的相对位置。"),
    "IMIN": ("距前低位置", "IdxMin($low,N)/N，N日最低价距当前的相对位置。"),
    "IMXD": ("高低点时序差", "(IdxMax(high,N)-IdxMin(low,N))/N，衡量高低点先后。"),
    "CORR": ("价量相关", "Corr($close,Log($volume+1),N)，价格与成交量相关性。"),
    "CORD": ("涨跌与量变相关", "Corr(close/Ref(close,1),Log(volume/Ref(volume,1)+1),N)。"),
    "CNTP": ("上涨天数占比", "Mean(close>Ref(close,1),N)，N日上涨日比例。"),
    "CNTN": ("下跌天数占比", "Mean(close<Ref(close,1),N)，N日下跌日比例。"),
    "CNTD": ("涨跌天数差", "上涨天数占比 - 下跌天数占比。"),
    "SUMP": ("上涨幅度占比", "上涨幅度总和 / 绝对涨跌幅总和，类似 RSI。"),
    "SUMN": ("下跌幅度占比", "下跌幅度总和 / 绝对涨跌幅总和。"),
    "SUMD": ("涨跌幅度差", "(上涨幅度总和-下跌幅度总和)/绝对涨跌幅总和。"),
    "VMA": ("成交量均线比", "Mean($volume,N)/$volume，N日均量相对当前量。"),
    "VSTD": ("成交量波动", "Std($volume,N)/$volume，N日成交量标准差归一。"),
    "WVMA": ("量权波动", "成交量加权的价格变化波动率。"),
    "VSUMP": ("放量占比", "成交量增加总和 / 成交量绝对变化总和。"),
    "VSUMN": ("缩量占比", "成交量减少总和 / 成交量绝对变化总和。"),
    "VSUMD": ("量变差值", "(放量总和-缩量总和)/成交量绝对变化总和。"),
}

QLIB_ALPHA360_MEANINGS = {
    "CLOSE": ("60日收盘序列", "Ref($close,N)/$close，过去 N 日收盘价相对当前收盘价。"),
    "OPEN": ("60日开盘序列", "Ref($open,N)/$close，过去 N 日开盘价相对当前收盘价。"),
    "HIGH": ("60日最高序列", "Ref($high,N)/$close，过去 N 日最高价相对当前收盘价。"),
    "LOW": ("60日最低序列", "Ref($low,N)/$close，过去 N 日最低价相对当前收盘价。"),
    "VWAP": ("60日均价序列", "Ref($vwap,N)/$close，过去 N 日成交均价相对当前收盘价。"),
    "VOLUME": ("60日成交量序列", "Ref($volume,N)/$volume，过去 N 日成交量相对当前成交量。"),
}

LOCAL_QLIB_ADAPTERS = [
    ("qlib_factor_score", "综合横截面因子分", "0.30*mom5 + 0.30*mom20 + 0.20*MA20_bias + 0.15*volume + 0.05*low_vol", "当前集成层用于龙头排序的 qlib 风格组合分。"),
    ("momentum_5d", "5日动量", "close / Ref(close, 5) - 1", "短线价格动量。"),
    ("momentum_20d", "20日动量", "close / Ref(close, 20) - 1", "波段价格动量。"),
    ("ma20_bias", "20日均线偏离", "close / Mean(close, 20) - 1", "衡量股价相对20日均线的强弱。"),
    ("volume_ratio_20d", "20日量比", "volume / Mean(volume, 20)", "衡量当前成交量相对近20日均量的放大程度。"),
    ("volatility_20d", "20日波动", "Std(close.pct_change(), 20)", "近20日收益率波动，用作风险惩罚项。"),
]


def prefix_name(name: str) -> str:
    return re.sub(r"\d+$", "", name)


def suffix_window(name: str) -> str:
    match = re.search(r"(\d+)$", name)
    return match.group(1) if match else ""


def row(
    project: str,
    family: str,
    name: str,
    category: str,
    meaning: str,
    formula: str = "",
    parameters: str = "",
    direction: str = "",
    score: Any = "",
    source_file: str = "",
    notes: str = "",
) -> dict[str, Any]:
    return {
        "project": project,
        "family": family,
        "name": name,
        "category": category,
        "meaning": meaning,
        "formula": formula,
        "parameters": parameters,
        "direction": direction,
        "score": score,
        "source_file": source_file,
        "notes": notes,
    }


def build_qlib_catalog() -> list[dict[str, Any]]:
    from qlib.contrib.data.loader import Alpha158DL, Alpha360DL  # type: ignore

    rows: list[dict[str, Any]] = []

    fields, names = Alpha158DL.get_feature_config()
    for name, formula in zip(names, fields):
        prefix = prefix_name(name)
        label, meaning = QLIB_ALPHA158_MEANINGS.get(prefix, (prefix, "qlib Alpha158 标准特征。"))
        window = suffix_window(name)
        rows.append(
            row(
                "qlib",
                "Alpha158",
                name,
                label,
                meaning,
                formula,
                f"window={window}" if window else "",
                source_file="microsoft-qlib/qlib/contrib/data/loader.py",
            )
        )

    fields, names = Alpha360DL.get_feature_config()
    for name, formula in zip(names, fields):
        prefix = prefix_name(name)
        label, meaning = QLIB_ALPHA360_MEANINGS.get(prefix, (prefix, "qlib Alpha360 标准序列特征。"))
        window = suffix_window(name)
        rows.append(
            row(
                "qlib",
                "Alpha360",
                name,
                label,
                meaning,
                formula,
                f"lag={window}" if window else "",
                source_file="microsoft-qlib/qlib/contrib/data/loader.py",
            )
        )

    rows.append(
        row(
            "qlib",
            "Label",
            "LABEL0",
            "未来收益标签",
            "下一交易区间收益率，用于模型训练标签，不是可提前使用的预测因子。",
            "Ref($close, -2)/Ref($close, -1) - 1",
            "label_horizon=1",
            source_file="microsoft-qlib/qlib/contrib/data/handler.py",
            notes="Alpha158/Alpha360 默认标签；实盘不可作为当期信号。",
        )
    )

    for name, category, formula, meaning in LOCAL_QLIB_ADAPTERS:
        rows.append(
            row(
                "qlib",
                "LocalAdapter",
                name,
                category,
                meaning,
                formula,
                source_file="lumen_qlib/sector_rotation_pipeline.py",
                notes="当前板块轮动集成层先用 AkShare 历史行情计算 qlib 表达式兼容信号。",
            )
        )
    return rows


def static_eval(node: ast.AST) -> Any:
    try:
        return ast.literal_eval(node)
    except Exception:
        return None


def extract_dict_appends(path: Path, target_names: set[str]) -> list[dict[str, Any]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    items = []
    for class_node in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
        for func in [n for n in class_node.body if isinstance(n, ast.FunctionDef) and n.name in target_names]:
            for call in ast.walk(func):
                if not isinstance(call, ast.Call):
                    continue
                if not isinstance(call.func, ast.Attribute) or call.func.attr != "append" or not call.args:
                    continue
                value = static_eval(call.args[0])
                if isinstance(value, dict) and "name" in value:
                    value["_function"] = func.name
                    items.append(value)
    return items


def build_lumen_catalog() -> list[dict[str, Any]]:
    from indicator_engine import INDICATOR_SPECS  # type: ignore
    from advanced_signals import ADVANCED_SIGNAL_CONFIG  # type: ignore

    rows: list[dict[str, Any]] = []
    for name, spec in INDICATOR_SPECS.items():
        rows.append(
            row(
                "LumenAlpha",
                "BaseIndicator",
                name,
                "基础技术指标",
                spec.get("definition", ""),
                formula=spec.get("definition", ""),
                parameters=spec.get("parameters", ""),
                source_file="LumenAlpha/stock_analyzer_project/indicator_engine.py",
                notes=spec.get("source", ""),
            )
        )

    signal_path = LUMEN_PATH / "indicators.py"
    for item in extract_dict_appends(signal_path, {"generate_signals", "_detect_combo_signals"}):
        family = "ComboSignal" if item.get("_function") == "_detect_combo_signals" else "SignalGenerator"
        score = item.get("score", "")
        notes = ""
        if family == "ComboSignal":
            notes = "组合信号在 generate_signals 中会乘以 1.5 后进入总分。"
        if item.get("win_rate"):
            notes = (notes + " " if notes else "") + f"代码内标注胜率 {item.get('win_rate')}%。"
        rows.append(
            row(
                "LumenAlpha",
                family,
                item.get("name", ""),
                item.get("combo_category") or item.get("category", ""),
                item.get("description", ""),
                direction=item.get("type", ""),
                score=score,
                source_file="LumenAlpha/stock_analyzer_project/indicators.py",
                notes=notes,
            )
        )

    advanced_descriptions = {
        "信号_缩量企稳MA5": "缩量企稳在 MA5 均线。",
        "信号_缩量企稳MA10": "缩量企稳在 MA10 均线。",
        "信号_缩量企稳MA20": "缩量企稳在 MA20 均线。",
    }
    tuple_desc = {
        "信号_弱转强": "龙头股调整后转强。",
        "信号_N型反包": "涨停后缩量回调再反包。",
        "信号_突破20日新高": "放量突破20日高点。",
        "信号_突破60日新高": "放量突破60日高点。",
        "信号_均线发散": "均线向上发散开启涨势。",
        "信号_量价齐升": "放量上涨量价配合。",
        "信号_放量站上MA20": "放量突破20日均线。",
        "信号_资金连续净流入": "主力资金连续3天流入。",
        "信号_换手率突增": "换手率大幅增加关注。",
        "信号_高换手率主力流入": "高换手且主力资金流入。",
        "信号_均线多头排列": "短期均线>中期均线>长期均线。",
        "信号_仙人指路": "上影线试盘可能启动。",
        "信号_早晨之星": "反转形态看涨。",
        "信号_突破盘整": "盘整后放量突破。",
        "信号_严重超跌": "短期大幅下跌可能反弹。",
        "信号_RSI极度超卖": "RSI<20 极度超卖。",
        "信号_KDJ极度超卖": "KDJ<10 极度超卖。",
        "信号_黄金坑": "挖坑后缩量回升。",
        "信号_缩量十字星": "变盘信号关注。",
        "信号_均线空头排列": "均线向下发散。",
        "信号_主力资金流出": "主力资金净流出。",
    }
    for name, cfg in ADVANCED_SIGNAL_CONFIG.items():
        display = name.replace("信号_", "")
        rows.append(
            row(
                "LumenAlpha",
                "AdvancedSignalGenerator",
                display,
                cfg.get("category", ""),
                advanced_descriptions.get(name) or tuple_desc.get(name, ""),
                direction=cfg.get("type", ""),
                score=cfg.get("weight", ""),
                source_file="LumenAlpha/stock_analyzer_project/advanced_signals.py",
            )
        )

    rows.append(
        row(
            "LumenAlpha",
            "CompositeScore",
            "lumen_total_score",
            "综合评分",
            "SignalGenerator.calculate_score 对所有触发信号分数求和，并映射为 极度强势/综合看多/偏多震荡/偏空震荡/多空平衡。",
            "sum(triggered_signal.score)",
            direction="mixed",
            source_file="LumenAlpha/stock_analyzer_project/indicators.py",
        )
    )
    return rows


def build_payload(items: list[dict[str, Any]]) -> dict[str, Any]:
    by_project = Counter(item["project"] for item in items)
    by_family = Counter(item["family"] for item in items)
    by_category = Counter(item["category"] for item in items)
    return {
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "notes": [
            "qlib 目录包含标准 Alpha158/Alpha360 特征族；qlib 也支持任意表达式，因此这里枚举的是本项目可直接程序化展开的标准输出。",
            "LumenAlpha 目录包含基础技术指标、普通信号、组合信号、高级形态信号和综合评分。",
            "LABEL0 是训练标签，不应作为实盘当期因子使用。",
        ],
        "stats": {
            "total": len(items),
            "byProject": dict(sorted(by_project.items())),
            "byFamily": dict(sorted(by_family.items())),
            "topCategories": dict(by_category.most_common(20)),
        },
        "items": items,
    }


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    WEB_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    items = build_qlib_catalog() + build_lumen_catalog()
    items = sorted(items, key=lambda item: (item["project"], item["family"], item["category"], item["name"]))
    payload = build_payload(items)

    json_path = OUTPUT_DIR / "factor_catalog_latest.json"
    csv_path = OUTPUT_DIR / "factor_catalog_latest.csv"
    js_path = WEB_OUTPUT

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    pd.DataFrame(items).to_csv(csv_path, index=False, encoding="utf-8-sig")
    js_path.write_text(
        "window.FACTOR_CATALOG = " + json.dumps(payload, ensure_ascii=False, indent=2) + ";\n",
        encoding="utf-8",
    )

    print(f"Factor catalog items: {len(items)}")
    print(f"JSON: {json_path}")
    print(f"CSV: {csv_path}")
    print(f"Web JS: {js_path}")
    print("By project:", dict(payload["stats"]["byProject"]))
    print("By family:", dict(payload["stats"]["byFamily"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
