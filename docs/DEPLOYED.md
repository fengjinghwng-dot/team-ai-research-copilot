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
LLM_ENABLED 仍为 false，不会产生模型调用。向量检索需要模型 Key 与 embedding 后才可用。
团队方向目前是明确的示例配置，管理员登录后应修改为实际方向。

## 还需要完成

1. 163 SMTP 授权码直接填入 Supabase 的 Password 并保存，再验证实际邮件送达。
2. 项目所有者使用指定邮箱实际登录，operator 核对已验证身份后初始化管理员，随后验收团队协作。
3. 确定模型 API、Key 和每天预算，完成黄金评测集后启用 AI 解读。
4. 如需 IM 群推送，另行配置机器人 webhook 和目标团队；站内日报默认不发外部消息。

SMTP 的主机、端口与发信账号已在浏览器表单中预填，尚不能据此宣称邮件登录已测试通过。
