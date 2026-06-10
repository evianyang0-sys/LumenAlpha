# LumenAlpha

LumenAlpha is an explainable A-share research toolkit that turns technical
indicators into industry-aware stock analysis.

Instead of treating a numerical score as the conclusion, LumenAlpha combines:

- a canonical technical-indicator engine;
- signal and event-based backtesting;
- industry and company-position context;
- trend, momentum, volume, volatility, and key price levels;
- explainable judgments with supporting evidence, counter-evidence, and
  invalidation conditions;
- daily and backtest HTML reports;
- optional SMTP delivery for daily reports.

## Highlights

- One calculation source for MA, EMA, AO, MACD, RSI, KDJ, CCI, ATR, VWAP, and
  Fibonacci zones.
- Industry-grouped research reports for the stock pool defined in
  `OPENCLAW_GUIDE.md`.
- Qualitative states such as trend continuation, recovery confirmation,
  range-bound observation, oversold watch, and downside risk.
- Backtest dashboards with win-rate heatmaps and methodology disclosure.
- Automated consistency and report-generation tests.

## Quick Start

```powershell
pip install -r stock_analyzer_project/requirements.txt

python -m stock_analyzer_project.stock_analyzer_main --codes 300750,600519

python -m stock_analyzer_project.guide_report `
  --guide "D:\trae_project\stock_analyzer_project\OPENCLAW_GUIDE.md"
```

Generated reports are written to:

```text
stock_analyzer_project/reports/daily/
stock_analyzer_project/reports/backtest/
```

## Tests

```powershell
python -m unittest discover -s stock_analyzer_project/tests -v
```

## Methodology

Technical signals are treated as evidence, not final recommendations. Research
reports combine sector characteristics, company positioning, trend structure,
momentum, volume participation, volatility, and explicit conditions that would
invalidate the current view.

See [indicator-audit.md](stock_analyzer_project/docs/indicator-audit.md) for the
canonical indicator definitions and the inconsistencies corrected in v1.

## Disclaimer

LumenAlpha is intended for research and education. Historical data and
technical analysis do not guarantee future performance and do not constitute
investment advice.
