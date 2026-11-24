# 第三方接口接入

第三方接口与 DeepSeek 官方接口单独配置，不沿用官方单价。
目前待接入地址为 `https://ai.cyai.asia/v1`，模型名 `deepseek-v4.1-flash-1017`。
接口可访问，模型调用的实际兼容性仍需 Key 和小样本验收。

Render Environment 和 GitHub repository variables 使用相同非密钥配置：

```dotenv
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=https://ai.cyai.asia/v1
LLM_API_FORMAT=chat_completions
CHEAP_MODEL=deepseek-v4.1-flash-1017
DEEP_MODEL=deepseek-v4.1-flash-1017
DAILY_BUDGET_CNY=20
DAILY_TOKEN_LIMIT=2500000
LLM_ENABLED=false
```

Key 直接填入 Render 的 `LLM_API_KEY` 和 GitHub `production` environment secret
`LLM_API_KEY`。请勿将第三方 Key 填进官方 Key 变量或提交到源码。

用户提供的“9.9/100M”目前是套餐/倍率信息，尚未确认有效输入、输出费率。
保持模型关闭，向平台核实币种、模型倍率、缓存/思考 Token、输入和输出分别如何扣费。
确认后，将包含全部倍率的人民币每百万 Token 单价分别配置为：

- `LLM_INPUT_CNY_PER_MILLION`
- `LLM_OUTPUT_CNY_PER_MILLION`

未确认费率时，自定义接口拒绝开启模型调用；后台显示预算目标和“待确认费率”。
确认后，按较高输入/输出费率计算所有预留 Token 的金额上限，再与 Token 配额取小值。
费用按配置费率估算，最终以平台账单为准，账户中其他程序的调用不包含在本项目限额内。

默认使用 Chat Completions + JSON Schema；也可明确配置 `LLM_API_FORMAT=responses`。
不自动切换协议或重试收费调用。结构化校验/原文引用校验失败的报告不会入库。
此接口未配置 embedding，保留关键词检索和按主题分组周报。

两处 Key、费率和显式启用完成后，先运行 Actions → Research pipeline → `sample`。
检查三篇真实报告与账单后，再跑完整日报。
