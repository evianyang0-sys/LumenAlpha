# LumenAlpha

A 股日线分析、信号回测与行业研究工具。项目使用单一指标引擎，并将量化信号作为研究证据而不是最终结论。

## 核心结构

```text
stock_analyzer_project/
├── indicator_engine.py     # 唯一基础指标计算源与指标口径注册表
├── indicators.py           # 信号评分与分析入口
├── advanced_signals.py     # 高级信号，基础指标仍由统一引擎提供
├── backtest.py             # 单信号与组合信号回测
├── reporting.py            # 回测/天级 HTML 报告
├── email_sender.py         # SMTP 邮件发送
├── daily_job.py            # 每日任务入口
├── reports/
│   ├── backtest/           # 回测报告
│   └── daily/              # 天级报告
└── tests/                  # 指标一致性与报告测试
```

## 指标统一口径

所有运行路径均通过 `indicator_engine.CanonicalIndicatorEngine` 计算基础指标。

| 指标 | 统一口径 |
|---|---|
| MA | 收盘价简单移动平均，5/10/20/50/200 日 |
| EMA | 收盘价指数移动平均，20/50/200 日 |
| AO | `SMA((最高+最低)/2, 5) - SMA((最高+最低)/2, 34)` |
| BBD | `(AO-SMA(AO,3))*100`，项目自定义动量派生项，不是真实资金流 |
| MACD | DIF=EMA12-EMA26，DEA=EMA(DIF,9)，MACD=2*(DIF-DEA) |
| RSI | Wilder 14 日递归平滑 |
| KDJ | RSV(9)，K/D 使用 `1/3` 递归平滑 |
| CCI | 典型价格 14 日均值和平均绝对偏差 |
| ATR | True Range 的 Wilder 14 日递归平滑 |
| VWAP | 日线序列累计典型价格成交量加权代理，不等同于分钟级当日 VWAP |
| FIB | 21 日滚动高低点回撤区间 |

完整机器可读定义位于 `INDICATOR_SPECS`。

## 安装

```bash
pip install pandas numpy baostock akshare tushare plotly tabulate
```

`baostock`、`akshare`、`tushare` 和 `plotly` 均按功能按需使用。Tushare Token 不再写入源码：

```powershell
$env:TUSHARE_TOKEN="your-token"
```

## 运行分析与报告

从项目父目录运行：

```powershell
python -m stock_analyzer_project.stock_analyzer_main --codes 300750,600519
python -m stock_analyzer_project.stock_analyzer_main --indices 000001,399006
python -m stock_analyzer_project.stock_analyzer_main --codes 300750 --backtest
```

每次成功分析都会生成：

- `reports/daily/daily_*.html`
- 启用 `--backtest` 时生成 `reports/backtest/*.html`

回测 HTML 包含胜率指标、持有周期热力图、分类筛选和指标定义。当前回测是固定持有期事件研究，不模拟完整资金曲线、手续费、滑点、涨跌停或资金占用，因此不会展示虚构的累计净值和最大回撤。

## 每日邮件

复制 `.env.example` 中的变量到系统环境。至少需要：

```text
STOCK_REPORT_CODES=300750,600519
STOCK_REPORT_EMAIL_TO=your-address@example.com
STOCK_REPORT_SMTP_HOST=smtp.example.com
STOCK_REPORT_SMTP_PORT=465
STOCK_REPORT_SMTP_USER=your-address@example.com
STOCK_REPORT_SMTP_PASSWORD=your-smtp-app-password
STOCK_REPORT_SMTP_SSL=true
```

手工验证：

```powershell
python -m stock_analyzer_project.daily_job
```

验证成功后可将同一命令配置为每天 20:00 执行。SMTP 密码应使用邮箱服务商提供的应用专用密码或授权码。

## 测试

```powershell
python -m unittest discover -s stock_analyzer_project/tests -v
```

测试会核对主分析与回测的指标列完全一致，并验证两类报告可独立生成。

## 风险说明

历史回测不代表未来表现。本项目仅用于研究，不构成投资建议。
