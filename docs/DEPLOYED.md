# 已部署环境

- 应用：[AI Research Copilot](https://team-ai-research-copilot.onrender.com)
- API 文档：[Swagger](https://team-ai-research-copilot.onrender.com/api/docs)
- API 基址：同源 `/api`，Next.js 转发到容器内部的 FastAPI。
- Supabase：新加坡，PostgreSQL 17.12，pgvector，私有 `copilot` schema，Data API 已关闭。
- Render：新加坡，Free，512 MB，Dockerfile.web；空闲后会休眠，首次请求有冷启动。
- GitHub：用户为前端协作将源码设为公开；数据库凭据只在 Render Environment 和 GitHub
  Production Secrets，源码与交付 ZIP 不含本项目实际密码或用户邮箱。

## 当前已经验证

- 19 张业务表及两份迁移，真实 Supabase 上可重复运行。
- 前端生产构建、依赖审计 0 漏洞、Linux 全栈 Docker 构建、30 项后端检查。
- 线上 `/api/healthz` 和 `/api/readyz` 返回 200；匿名 `/api/v1/me` 返回 401。
- 真实 Chrome 中邮箱表单可见，无 JavaScript 错误，无生产 Mock 横幅。
- ES256 JWKS 与邮箱 provider 的公开接口可访问，站点 URL 与同域回调已配置。
- 首轮真实源入库 60 篇、短名单 20 篇；Semantic Scholar 本轮请求失败，已记录 warning 并回退。

## 启用状态

每日北京时间 08:30 的 GitHub Actions 元数据流水线已启用，另有周五组会列表和周日周报任务。
LLM_ENABLED 仍为 false，不会产生模型调用。用户选择 DeepSeek V4.1 Flash、每天 20 元；
适配与保守额度保护见 [DeepSeek 配置](DEEPSEEK.md)。Key 尚待创建，未实调模型。
向量检索需要另配 embedding；DeepSeek 解读接口不提供这项能力。
团队方向目前是明确的示例配置，管理员登录后应修改为实际方向。

## 还需要完成

1. 163 SMTP 已由用户保存，页面显示已存储密码；仍需验证实际邮件送达。
2. 已核对用户指定的已验证邮箱并初始化首位管理员；待用修复后的最新邮件完成浏览器登录验收。
3. 创建 DeepSeek Key 并填入云端，验收真实解读与黄金评测集。
4. 如需 IM 群推送，另行配置机器人 webhook 和目标团队；站内日报默认不发外部消息。

尚不能仅根据 SMTP 保存状态宣称邮件登录已测试通过。

## 邮件回调配置

`WORKSPACE_URL` 必须是公开 HTTPS 域名，供服务端回调生成跳转地址；Render 容器内部的
`0.0.0.0:10000` 不能作为浏览器目的地。Magic link 和 Confirm sign up 两个邮件模板使用
仓库中的 `deploy/auth-email.html`，指向 `/auth/confirm?token_hash=...&type=email`。
此路由执行 Supabase 一次性 Token 验证并写入会话 Cookie；OAuth 仍使用 `/auth/callback`
交换 PKCE code。更换模板后应重新申请邮件，旧邮件可能已失效。

修复版本 `5f6761f` 已发布；线上 `/auth/callback` 和 `/auth/confirm` 的缺参／失效链接
均返回公开域名的登录页，健康检查通过。云端 36 项后端测试和 4 项回调测试通过。
