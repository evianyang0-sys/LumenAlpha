# LumenAlpha 与 Qlib 合并优化方案

日期：2026-06-17

## 结论

不建议把两个项目的源码直接混合。更合理的方式是：

1. 保留 `microsoft-qlib` 作为量化底座，负责数据规范化、特征工程、模型训练、组合回测、交易成本、实验记录和绩效评估。
2. 保留 `LumenAlpha` 作为 A 股行业研究与解释层，迁移其技术指标、信号解释、板块池和 HTML 报告能力。
3. 新建一个轻量集成层，例如 `lumen_qlib/`，专门实现数据适配、板块轮动因子、二层组合策略和报告导出。

目标不是“更复杂”，而是让收益假设可重复检验：先做板块择时，再做板块内选股，最后用组合级回测验证真实净值、回撤、换手、交易成本和相对基准收益。

## 两个项目分工

### LumenAlpha 适合保留的部分

- `stock_analyzer_project/indicator_engine.py`：统一技术指标口径，适合转成 qlib feature 或离线特征生成器。
- `stock_analyzer_project/indicators.py`：信号评分逻辑可保留，但需要避免直接把人工分数当最终交易信号。
- `stock_analyzer_project/OPENCLAW_GUIDE.md`：当前手工主题/板块股票池，可以作为第一版板块配置。
- `stock_analyzer_project/research_reporting.py` 与 `reporting.py`：解释性日报、行业研究报告和回测报告可以继续使用。

### LumenAlpha 需要弱化或改造的部分

- `data_fetcher.py` 只抓最近约 365 天，不适合严肃训练和滚动回测。
- `backtest.py` 和 `combo_backtest.py` 主要是事件研究/固定持有期统计，不是组合资金曲线回测。
- 当前板块映射偏手工维护，适合研究观察，不适合自动化实盘。
- `guide_report.py` 的股票池解析锚点仍在找旧标题 `## 批量分析命令`，但当前指南文件后续标题是 `## 大盘与单股分析`，需要修复后日报才能稳定运行。

### Qlib 适合作为底座的部分

- `qlib/data`：统一行情、特征、标的池读取。
- `qlib/model` 与 `examples/benchmarks/LightGBM`：先用 LightGBM/Alpha158 或 Alpha360 做稳健基线。
- `qlib/contrib/strategy/signal_strategy.py`：`TopkDropoutStrategy` 可做股票打分组合，`WeightStrategyBase` 更适合做板块权重策略。
- `qlib/backtest`：组合级回测、交易成本、持仓、成交、净值曲线。
- `qlib/backtest/profit_attribution.py`：行业/板块维度归因可以复用，但它自身标注维护状态一般，建议只作为参考或二次封装。

## 推荐架构

```text
qlib/
├── LumenAlpha/              # 原项目，作为领域逻辑来源
├── microsoft-qlib/          # 原 qlib，上游底座
└── lumen_qlib/              # 建议新增集成层
    ├── data/
    │   ├── dump_a_share_to_qlib.py
    │   ├── sector_membership.csv
    │   └── sector_index_builder.py
    ├── factors/
    │   ├── lumen_technical.py
    │   ├── sector_momentum.py
    │   └── sector_breadth.py
    ├── strategies/
    │   └── sector_rotation_strategy.py
    ├── reports/
    │   └── qlib_lumen_report.py
    └── configs/
        ├── baseline_lightgbm.yaml
        └── sector_rotation.yaml
```

## 板块轮动策略设计

### 第一层：板块选择

每周或每月调仓，给每个板块一个分数：

- 动量：20/60/120 日收益、相对沪深 300 或中证 500 的超额收益。
- 趋势：板块指数是否站上 MA20/MA60，斜率是否转正。
- 广度：板块内上涨家数占比、站上 MA20 的股票占比。
- 量能：板块成交额相对 20 日均值变化。
- 风险惩罚：板块波动率、最大回撤、拥挤度和近期急涨。

建议初版规则：

```text
sector_score =
  0.35 * rank(ret_20_excess)
+ 0.25 * rank(ret_60_excess)
+ 0.20 * rank(breadth_ma20)
+ 0.10 * rank(volume_ratio)
- 0.10 * rank(volatility_20)
```

每期选择 Top 2 到 Top 4 个板块，单板块权重上限 30% 到 40%，整体仓位由市场状态决定。

### 第二层：板块内选股

板块内使用 LumenAlpha 技术信号与 qlib 预测分融合：

```text
stock_score =
  0.45 * qlib_model_score
+ 0.25 * lumen_trend_score
+ 0.15 * volume_confirmation
+ 0.15 * risk_adjusted_momentum
```

每个入选板块持有 3 到 8 只股票，避免一个主题只靠单一个股驱动。高弹性主题如光模块、PCB、机器人、算力应设置更严格的止损和权重上限。

### 第三层：组合与风控

- 调仓频率：先用周频，避免日频轮动导致成本吞噬收益。
- 单股上限：5% 到 8%。
- 单板块上限：30% 到 40%。
- 最大换手：单期不超过 30% 到 50%。
- 市场过滤：沪深 300 或中证 500 低于 MA60 且 MA60 下行时降低总仓位。
- 成本假设：A 股至少纳入佣金、印花税、滑点、涨跌停不可成交。

## 实施优先级

1. 先打通环境和数据：安装 qlib/LumenAlpha 依赖，准备可覆盖至少 5 年的 A 股日线和复权数据。
2. 修复 LumenAlpha 当前可运行性问题：尤其是 `guide_report.py` 的股票池解析锚点。
3. 将 `OPENCLAW_GUIDE.md` 的板块池拆成结构化 CSV，字段至少包含 `code,name,sector,weight_cap,is_high_beta`。
4. 构建板块指数：用等权或流通市值权重生成板块收益序列。
5. 先做无机器学习版规则轮动，验证板块层 alpha 是否真实存在。
6. 再叠加 qlib LightGBM 股票打分，验证是否提升收益/回撤比。
7. 最后把 LumenAlpha 报告层接到 qlib 回测输出，生成“板块选择原因 + 持仓解释 + 绩效归因”的日报。

## 验收指标

不要只看年化收益，至少同时看：

- 年化收益、最大回撤、夏普、卡玛。
- 超额收益、信息比率、胜率。
- 换手率、交易成本占收益比例。
- 板块暴露是否过度集中。
- 不同市场阶段表现：牛市、震荡市、熊市。
- Walk-forward 稳定性：参数在训练期好，验证期也不能明显失效。

## 风险提醒

更高收益通常来自承担更多风险或更好的信息优势。板块轮动尤其容易犯三个错误：用未来成分股造成幸存者偏差、用短期热门主题过拟合、忽视换手和涨跌停造成的真实成交约束。所有策略都应先以研究和模拟为主，不构成投资建议。
