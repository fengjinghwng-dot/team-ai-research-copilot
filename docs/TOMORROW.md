# 下一步：接入 DeepSeek 并验收真实解读

## 今晚已准备

- 邮箱邀请与撤销、成员角色调整和移出；邀请仅授予普通成员，七天有效。
- 收藏、已读、私有笔记及知识库筛选；其他成员无法读取个人记录。
- 输入、输出、缓存 Token 统计，以及按当前 Flash 高峰价估算的费用上界。
- 周报可按团队方向分组，不需要等待 embedding；页面会标明分组依据。
- 个人日报支持 Resend 或直接 SMTP；凭据未配置时不会发送。
- GitHub 手动任务新增 `sample`，只处理三篇已有论文，不推送外部消息。
- 真实全文缓存和十篇未标注评测候选；没有编造专家评价或模型结果。

## 接入模型

1. 在 [DeepSeek 控制台](https://platform.deepseek.com/api_keys)创建 Key，并保证 API 账户有可用余额。
2. 同一 Key 直接填写到两个云端配置中，不发到聊天或源码：
   - Render 当前服务 → Environment → `DEEPSEEK_API_KEY`。
   - GitHub 当前仓库 → Settings → Environments → `production` → Secret `DEEPSEEK_API_KEY`。
3. 两处的非密钥配置：`LLM_PROVIDER=deepseek`、`CHEAP_MODEL=deepseek-flash`、
   `DEEP_MODEL=deepseek-flash`、`DAILY_BUDGET_CNY=20`、`DAILY_TOKEN_LIMIT=2500000`。
   上述值已在部署准备配置中设置；Render 与 GitHub 使用一致配置。
4. 要开始试跑时，Render 的 `LLM_ENABLED` 环境变量和 GitHub 同名 repository variable 改为 `true`。
   Render 保存时选择部署；GitHub 到 Actions → Research pipeline → Run workflow → `sample`。
5. 查看管理后台任务与费用，打开生成报告的论文检查：事实引用、局限具体性、假设实验设计。
   小样本通过后再手动运行 `daily`；日常定时任务保持北京时间 08:30。

每天 20 元为本项目的保守保护上限。界面显示的是高峰单价费用估算上界，
不是 DeepSeek 账单；其他程序使用同一 Key 的消费不包含在本项目限额里。

## 仍需你的选择或账号配置

- 管理后台将示例研究方向改为团队实际方向；确认评测候选是否有代表性，并填写专家标签。
- 选择飞书、企微或 Slack 后配置机器人 webhook 与目标团队，才会发群日报。
- 个人日报发信是独立配置。已有 Supabase SMTP 用于登录邮件；不会读取或提取其中的授权码。
  如选 163 直接发日报，需要另外把 SMTP_HOST、SMTP_USERNAME、SMTP_PASSWORD 和 EMAIL_FROM
  填入工作任务的云端配置；发信需用户主动订阅。
- 真正的语义检索仍需要独立 embedding 模型。主题分组周报不会伪装成向量检索。
- Google/飞书/企微 SSO 需要对应应用的 Client ID / Secret；邮箱登录可先满足团队使用。

## 验收边界

已完成的浏览器检查使用清楚标记的本地演示数据；数据库权限、私有笔记和预算隔离另有
真实 PostgreSQL 集成测试。两个实际成员的线上使用与 DeepSeek 真调用，仍需接入后验收。
所有付费模型调用在今晚保持关闭。
