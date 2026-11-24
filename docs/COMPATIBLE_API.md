# 第三方接口接入

第三方接口与 DeepSeek 官方接口单独配置，不沿用官方单价。
当前地址为 `https://ai.cyai.asia/v1`，模型名 `deepseek-v4.1-flash-1017`。
2026-11-24 用户明确改为每天 20M Token，取消金额限额，已启用模型调用。

Render Environment 和 GitHub repository variables 使用相同非密钥配置：

```dotenv
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=https://ai.cyai.asia/v1
LLM_API_FORMAT=chat_completions
LLM_THINKING_MODE=disabled
CHEAP_MODEL=deepseek-v4.1-flash-1017
DEEP_MODEL=deepseek-v4.1-flash-1017
BUDGET_MODE=tokens
DAILY_TOKEN_LIMIT=20000000
LLM_ENABLED=true
```

Key 直接填入 Render 的 `LLM_API_KEY` 和 GitHub `production` environment secret
`LLM_API_KEY`。请勿将第三方 Key 填进官方 Key 变量或提交到源码。
`LLM_API_KEY` 需要用户自己新增；`LLM_API_FORMAT` 用于选择请求协议，是独立配置。

填好后，可运行 Actions → Research pipeline → `check`（手动默认项）。它只请求模型列表
`GET /models`，检查 Key 和目标模型是否列出；不开启生成、不发送论文、不回显 Key 或服务商错误正文。
检查通过仅表示模型目录可访问，真正的 JSON Schema 解读兼容性仍需后续小样本验收。

2026-11-24，已确认 Render 变量和 GitHub `production` Secret 存在。
[真实目录检查](https://github.com/fengjinghwng-dot/team-ai-research-copilot/actions/runs/45328737808)
返回 HTTP 200，Key 被接受，`deepseek-v4.1-flash-1017` 已列出；生成请求为 0。
同时修复了环境变量中的 SMTP 端口字符串解析，避免定时任务在模型检查前退出。

当前按输入与输出 Token 合计，每天北京时间 00:00 重置；全体成员、Worker 与 API 共用
20,000,000 上限，当前团队配额也为 20,000,000。调用前按保守上界原子预留，再结算实际用量；
未知收费结果保留预留。Token 模式不使用 `DAILY_BUDGET_CNY`、费率或金额熔断，后台隐藏金额估算。
账户中其他程序的调用不包含在本项目配额里。

若未来改回 `BUDGET_MODE=currency`，则须先确认含全部倍率的输入/输出人民币每百万 Token
单价，配置 `LLM_INPUT_CNY_PER_MILLION` 和 `LLM_OUTPUT_CNY_PER_MILLION` 后才能启用。

默认使用 Chat Completions + JSON Schema；也可明确配置 `LLM_API_FORMAT=responses`。
不自动切换协议或重试收费调用。结构化校验/原文引用校验失败的报告不会入库。
此接口未配置 embedding，保留关键词检索和按主题分组周报。

Chat 请求显式关闭思考，报告输出上限为 6,000 Token，相关性粗排仍为 1,000。
返回截断时，若 SDK 提供已知用量则结算该用量；未知结果继续保留预留。
精确引用存在于其他已提供章节时可修正锚点，不会改写引用或接受原文不存在的引用。
通过 Actions → Research pipeline → `sample` 检查三篇真实报告；日报和周报按原定时任务运行。
当前 `sample` 仅给这三篇做有限相关性评分，避免试跑时扩散到完整候选池。
全文报告从原文抽取的引用目录选择编号，系统回填原句，再执行引用校验；摘要报告仍使用原句引用。
[真实验收](https://github.com/fengjinghwng-dot/team-ai-research-copilot/actions/runs/45334023151)
已通过 3/3 相关性评分和 3/3 报告：一篇 PDF 精读、两篇摘要解读。
[周报验收](https://github.com/fengjinghwng-dot/team-ai-research-copilot/actions/runs/45334029889)
已生成三条按主题分组的跨论文假设，均标记待验证。
