# 全云端部署

## 需要的连接

1. GitHub：存私有仓库，建议名 `team-ai-research-copilot`。默认分支 main。
2. Supabase：PostgreSQL、pgvector、Auth。选择离 API 接近且团队可访问的区域。
3. Render：Docker Web Service，使用 `render.yaml`。会创建付费 starter 实例，创建前
   应以账号实际报价确认。代码已备好，并未创建计费资源。
4. 模型服务：可用的 OpenAI API key 和模型权限。key 放云端 Secrets，不发聊天。
5. 可选：Google OAuth 应用、飞书/企微/Slack webhook、Resend 已验证发信域。

## 操作顺序

### 1. 推 GitHub

将本项目根目录作为仓库根目录。排除 `.env`、虚拟环境、缓存与个人数据。
前端 agent 在同仓库 `frontend/` 工作，不需要共享后端的数据库密码。
本项目已推送到私有仓库 [fengjinghwng-dot/team-ai-research-copilot](https://github.com/fengjinghwng-dot/team-ai-research-copilot)，
默认分支 main，真实 PostgreSQL CI 已通过。后续修改继续从 D 盘项目提交并推送即可。

### 2. Supabase

- 创建项目后取得 direct 或 **session pooler** PostgreSQL 连接串；不要使用 transaction
  pooler。将协议写成 `postgresql+psycopg://...`，启用 `sslmode=require`。
  密码中的 `@`、`#` 等字符须 URL 编码。迁移需要创建 schema/extension 的权限。
- `copilot migrate` 会创建私有 `copilot` schema、vector 扩展、表、HNSW 索引和校验约束。
- 不要把 `copilot` 添加到 Supabase Exposed schemas；anon/authenticated 无此 schema 权限。
- Auth 选择 Google（第一版），使用非对称 ES256/RS256 signing key，配置站点 URL 和
  `/auth/callback` 允许地址。飞书/企微自定义 SSO 尚未做实际账号联调；不是仅填 webhook。
- 先用前端登录或 Supabase Auth 创建管理员账号，取得真实 UUID，然后运行：

```sh
copilot bootstrap --name "研究组" --admin-id ACTUAL_AUTH_UUID --admin-email ACTUAL_EMAIL
```

记录返回的 team_id。示例主题需要管理员在配置页替换。成员首次登录并调用 `/v1/me`
后，由管理员通过 `/members` API 加入团队；没有开放的自动加入或自助提权接口。

### 3. Render API

- 连接 GitHub，New Blueprint 指向 `render.yaml`。使用 Docker，迁移命令 `copilot migrate`。
- Secrets 填 `DATABASE_URL`、`SUPABASE_URL`，`CORS_ORIGINS` 用 JSON 字符串数组，
  `WORKSPACE_URL` 填前端正式地址。
- 初期 `LLM_ENABLED=false`。Render API 使用 embedding 搜索时才需要模型 key；如启用
  语义检索，API 与 Actions 应使用同一模型和预算配置，不共享内存计数器，账本在 DB。
- 部署后检查 `/healthz`、`/readyz` 和 `/docs`。`readyz` 表示数据库与迁移可用，SSO 字段
  表示配置存在，不替代真实登录验证。
- Worker 在 Actions 执行，不通过公开 HTTP 管理端点触发。后端不依赖本机持续开机。

### 4. GitHub Actions

创建 production Environment；Secrets/Variables 参考 `.github/workflows/pipeline.yml`。
把数据库密码和 API key 放 Secrets，主题/模型 ID/域名等放 Variables。
先保持 `PIPELINE_ENABLED` 未设置，手动检查迁移和 CI。

准备启用时设 `PIPELINE_ENABLED=true`，最初 `LLM_ENABLED=false` 跑每日抓取。
确认真实数据质量后再开启模型并调小 `DAILY_TOKEN_LIMIT`、团队配额试运行。
每日定时为北京时间 08:30，周五 16:00 保存组会 Reading List，周日 10:00 生成趋势周报。
GitHub Actions 并非准时调度 SLA。仓库禁用或运行额度耗尽
会停止调度。严格准点可之后改为云平台 Cron，命令仍是 `copilot daily/weekly`。

### 5. IM / 邮件

IM_PROVIDER 三选一，IM_WEBHOOK_URL 放 Secrets，IM_TEAM_ID 为目标团队 UUID。
当前每个部署仅配置一个群 webhook；增加多个团队群需扩展为加密的团队级 integration 表。
群消息最多 5 篇，按钮进入已登录工作台再认领；直接回调认领需要额外 IM 身份绑定。
个人站内日报默认保存；邮件需 Resend key、已验证 EMAIL_FROM、用户 email_opt_in=true。
未知发送结果记 uncertain，避免重试刷屏；运营者核实后才能显式处理该 delivery 记录。

## 上线前验证

- 跑真实 arXiv/HF/S2，确认限流回退、缓存命中、首次提交过滤；数量不足如实显示。
- 真实数据库跑 CI 全套集成测试，再用两位实际 SSO 用户验证 team scopes。
- 完成 `evals/golden_set.example.jsonl` 的 10 篇专家评测，不能把空模板当已通过。
- 低预算验证 deep → medium → metadata 降级，检查 used/reserved 与 provider 账单抽样一致。
- 用指定测试群与邮箱验证一次推送，核对 team_id、域名和去重记录。
- 前端更新 CORS、OAuth redirect URL、WORKSPACE_URL；将敏感配置限制给管理员。
- 数据库启用平台可用的备份/恢复能力；持续监控 job_runs.failed/degraded 和 uncertain 调用。

## 限制

此代码没有完成真实云端部署、真实登录或模型实测。运行环境和流水线会产生供应商费用，
Actions 私有仓库额度及 Supabase/Render 费用以账号为准。Token 熔断不等于美元硬上限。
当前免费文本搜索支持关键词匹配，向量检索需要已生成 embedding；不支持任意上传私有 PDF。
