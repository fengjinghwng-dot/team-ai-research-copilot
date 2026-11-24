# 已部署环境

- 应用：[AI Research Copilot](https://team-ai-research-copilot.onrender.com)
- API 文档：[Swagger](https://team-ai-research-copilot.onrender.com/api/docs)
- API 基址：同源 `/api`，Next.js 转发到容器内部的 FastAPI。
- Supabase：新加坡，PostgreSQL 17.12，pgvector，私有 `copilot` schema，Data API 已关闭。
- Render：新加坡，Free，512 MB，Dockerfile.web；空闲后会休眠，首次请求有冷启动。
- GitHub：用户为前端协作将源码设为公开；数据库凭据只在 Render Environment 和 GitHub
  Production Secrets，源码与交付 ZIP 不含本项目实际密码或用户邮箱。

## 当前已经验证

- 21 张业务表及四份迁移，真实 Supabase 上可重复运行。
- 前端生产构建、依赖审计 0 漏洞、Linux 全栈 Docker 构建、47 项后端与 4 项浏览器检查。
- 线上 `/api/healthz` 和 `/api/readyz` 返回 200；匿名 `/api/v1/me` 返回 401。
- 真实 Chrome 中邮箱表单可见，无 JavaScript 错误，无生产 Mock 横幅。
- ES256 JWKS 与邮箱 provider 的公开接口可访问，站点 URL 与同域回调已配置。
- 首轮真实源入库 60 篇、短名单 20 篇；Semantic Scholar 本轮请求失败，已记录 warning 并回退。

## 启用状态

每日北京时间 08:30 的 GitHub Actions 元数据流水线已启用，另有周五组会列表和周日周报任务。
LLM_ENABLED 仍为 false，不会产生模型调用。用户选择 DeepSeek V4.1 Flash、每天 20 元；
适配与保守额度保护见 [DeepSeek 配置](DEEPSEEK.md)。Key 尚待创建，未实调模型。
向量检索需要另配 embedding；周报可先按团队主题分组，并标明依据。
团队方向目前是明确的示例配置，管理员登录后应修改为实际方向。

## 还需要完成

1. 163 登录邮件已由用户实际收到，中文模板已重新加载逐字核对；个人日报发信另行配置。
2. 已核对用户指定的已验证邮箱并初始化首位管理员；待用修复后的最新邮件完成浏览器登录验收。
3. 创建 DeepSeek Key 并填入云端，验收真实解读与黄金评测集。
4. 如需 IM 群推送，另行配置机器人 webhook 和目标团队；站内日报默认不发外部消息。

修复后完整浏览器会话和两位实际成员的线上使用仍需验收。

## 邮件回调配置

登录方式已补齐邮箱密码：已有账号先用邮件登录，在团队选择页或个人设置中设置密码。
之后可直接用邮箱和工作台密码登录。登录状态使用持久 Cookie 和刷新中间件续期；
主动退出后需重新认证。密码由 Supabase Auth 管理，不进入业务数据库。

`WORKSPACE_URL` 必须是公开 HTTPS 域名，供服务端回调生成跳转地址；Render 容器内部的
`0.0.0.0:10000` 不能作为浏览器目的地。Magic link 和 Confirm sign up 两个邮件模板使用
仓库中的 `deploy/auth-email.html`，指向 `/auth/confirm?token_hash=...&type=email`。
此路由执行 Supabase 一次性 Token 验证并写入会话 Cookie；OAuth 仍使用 `/auth/callback`
交换 PKCE code。更换模板后应重新申请邮件，旧邮件可能已失效。

修复版本 `5f6761f` 已发布；线上 `/auth/callback` 和 `/auth/confirm` 的缺参／失效链接
均返回公开域名的登录页，健康检查通过。云端 36 项后端测试和 4 项回调测试通过。

## 最新功能版本

`44d7fcb` 已发布：默认邮箱密码登录，支持在团队选择页和个人设置中设置密码。
持久会话和 Next.js 15 刷新中间件已加入，邮件登录保留备用。线上浏览器已确认两个入口可见、
无 JavaScript 错误、无生产 Mock。云端检查：47 项后端、5 项回调/跳转、4 项工作台交互、
3 项认证流程全部通过；认证检查使用隔离测试服务和真实 SDK，未设置或读取实际用户密码。

`4b61bc3` 已在现有免费服务发布，邮箱邀请、个人阅读状态、接入状态接口已在线确认。
数据库四份迁移已应用，匿名业务访问返回 401，`readyz` 显示模型仍关闭。
本次云端检查为 47 项后端、4 项浏览器流程、4 项回调测试通过；完整 Linux 容器构建成功。
浏览器流程使用明确标记的演示数据；实际成员与模型 Key 接入后的验收步骤见 [TOMORROW.md](TOMORROW.md)。
