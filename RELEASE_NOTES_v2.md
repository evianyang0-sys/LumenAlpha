# v2 Release Notes

## 版本定位

v2 是“板块轮动研究台”的第一版可交付闭环：从人气榜采集、科技板块重分类、统一信号计算，到可视化页面和 DeepSeek 尾端分析入口全部打通。

## 可视化页面标注

- 龙头天梯：展示个股龙头强度、涨停梯队、显著信号标签；点击个股后右侧出现 30 日 K 线。
- 板块曲线：按科技细分板块和非科技一级板块展示趋势；点击板块后展示成分股与板块 K 线。
- 统一信号：合并 qlib 与 LumenAlpha 信号，支持搜索并尽量去除同一股票重复展示。
- 日报分析：展示本地分析 agent 生成的板块强弱、风险点和观察清单。
- 因子图谱：列出 qlib 与 LumenAlpha 可输出因子及含义，标记来源。
- 数据复盘：展示采集覆盖、历史 K 线成功率、失败原因和每日刷新风险。
- 项目合并：解释两个项目如何在信号、数据和报告层合并。

## 技术变化

- 新增 `lumen_qlib/sector_rotation_pipeline.py`，统一生成龙头卡片、板块汇总、板块时间序列和信号流。
- 新增 `lumen_qlib/factor_catalog.py`，汇总 qlib 与 LumenAlpha 因子目录。
- 新增 `scripts/daily_refresh_sector_rotation.py`，支持 daily/weekly/pipeline-only/analysis-only 模式。
- 新增 DeepSeek API 代理接口 `POST /api/ai/analyze`，只使用本地环境变量 `DEEPSEEK_API_KEY`。
- 新增 dashboard server，支持静态文件、Markdown MIME、DeepSeek mock 模式和 AI 分析缓存。

## 运行验证

- LumenAlpha 单测：8 passed。
- qlib 选定单测：41 passed。
- 前端语法检查：`node --check app.js` 与 `node --check server.mjs` passed。
- 本地页面检查：主要页面、tab 跳转、个股 K 线、板块 K 线、无 key/Mock DeepSeek 状态均完成验证。
