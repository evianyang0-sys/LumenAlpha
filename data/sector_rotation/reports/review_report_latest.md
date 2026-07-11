# Sector Rotation Output Review

Generated: 2026-07-11T18:25:46

## Data Health
- Reclassified rows: 2000
- Tech rows: 579
- Selected boards: 20
- Selected stocks: 152
- History OK: 150/152
- History missing: 2
- Unified signal rows: 760
- Boards with curves: 20

## Review Findings
- The tech taxonomy is now useful enough for PCB/CPO/liquid-cooling/AI-compute separation.
- LumenAlpha and qlib-style signals are joined through a long-form table with explicit source labels.
- Cross-sectional percentile scoring is used for qlib, LumenAlpha, and sector-trend components to keep sources comparable.
- Some board curves are approximations from hot leaders, not official board indices.
- qlib native data import remains the next major step before serious backtesting.

## Known Issues
- 当前全 A qlib bin 数据尚未导入；第一版 qlib 信号使用 qlib 表达式兼容公式在 AkShare 历史行情上计算。
- 科技细分 taxonomy 仍需持续校准，尤其是 其他电子通信 与 消费电子 的边界。
- 板块时间曲线使用每个板块人气前若干股票等权近似，不等同于正式指数。
- 本轮有 2 只股票历史行情未成功拉取，主要表现为历史行情接口错误或无返回；对应个股的 qlib/LumenAlpha 分数会降级。