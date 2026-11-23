# DeepSeek Flash 接入与每天 20 元保护

用户选择 DeepSeek V4.1 Flash，官方 API 模型名为 `deepseek-flash`。
官方入口：[创建 Key](https://platform.deepseek.com/api_keys)、
[人民币价格](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)、
[Responses API](https://api-docs.deepseek.com/guides/responses_api/)。

Render Environment 与 GitHub repository variables 配置：

```dotenv
LLM_PROVIDER=deepseek
CHEAP_MODEL=deepseek-flash
DEEP_MODEL=deepseek-flash
DAILY_BUDGET_CNY=20
DAILY_TOKEN_LIMIT=2500000
LLM_ENABLED=false
```

Key 直接填入 Render Environment 的 `DEEPSEEK_API_KEY` 和 GitHub **production**
environment secret `DEEPSEEK_API_KEY`。不要提交到源码、文档、截图或聊天。
两处完成后再把 `LLM_ENABLED` 改为 true；先跑少量真实论文验收，不自动重试收费请求。

## 上限如何执行

按 2026-11-24 查到的当前价格，Flash 高峰未缓存输入为 2 元/百万 tokens，输出为
8 元/百万 tokens。为保守控制支出，把所有输入、输出和未知收费调用的预留 Token
都按更贵的 **8 元/百万** 折算。因此 20 元对应 250 万 Token，且仍受更小的
`DAILY_TOKEN_LIMIT` 和团队 Token 额度约束。不是实际账单的费用统计，通常会提前停止。

预留在 PostgreSQL 中加锁；多个团队、GitHub 定时任务和 API 共用全局额度。
调用超时保留预留；超预算时降级为摘要或元数据。当前适配只允许 `deepseek-flash`，
避免换成更贵的模型后继续沿用旧单价。价格变化需要重新核对单价和上限。
第三方账户中其他程序的调用不包含在本项目额度内。

实际费用示例：100 万未缓存输入 + 10 万输出，空闲时段约 1.4 元，高峰约 2.8 元。
每天 5 篇全文精读 + 15 篇摘要解读的成本仍取决于全文长度与输出；不能将估算当账单。
北京时间 08:30 启动处于当前空闲时段；长任务跨入 09:00 后仍按高峰上限保护。

## 功能边界与验证状态

- Responses API 使用 JSON Schema / Pydantic 校验，初始关闭思考以保留结构化输出预算。
- DeepSeek 暂无本项目可用的 embedding 接口；不会把向量请求误发给它。
  AI 论文解读、关键词检索和协作可用，语义检索与向量趋势聚类待另配 embedding 模型。
- Key 尚待用户创建；模型请求只做了测试替身验证，未宣称真实 DeepSeek 调用成功。
- 人工标注的黄金评测集尚未完成；原文引用校验不等于研究判断已通过专家验收。
