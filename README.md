# Team AI Research Copilot

团队共享论文解析、方向推荐、组会认领与立项灵感池的云端工作台，已集成 Next.js 前端。

在线应用：[AI Research Copilot](https://team-ai-research-copilot.onrender.com)。
源码：[fengjinghwng-dot/team-ai-research-copilot](https://github.com/fengjinghwng-dot/team-ai-research-copilot)。
[GitHub Actions](https://github.com/fengjinghwng-dot/team-ai-research-copilot/actions/runs/45334002489) 已在 PostgreSQL 17 上通过 70 项后端测试，另有 7 项工作台流程、6 项认证/入组流程与 5 项回调检查。
AI 已启用，按每天 20M 输入+输出 Token 控制全团队用量，未启用金额限额。

成员入组支持两种方式：登录后在团队选择页提交申请，由管理员在“管理后台 → 入组申请”
点击通过/拒绝；或由管理员预先创建邮箱邀请。开放申请由管理员在团队配置中控制。
团队名称也可由管理员在同一配置页修改，支持中文，长度为 1–120 个字符。

## 先读这些文件

- `docs/FRONTEND_HANDOFF.md`：直接交给前端 agent 的功能、路由、文件和交互要求。
- `docs/CLOUD_DEPLOY.md`：Supabase + Render + GitHub Actions 云端部署步骤与所需连接。
- `SPEC.md`：缓存边界、权限、评分、预算和验收标准。
- `docs/STATUS.md`：已验证内容与仍需真实账号验证的内容。
- `docs/TOMORROW.md`：DeepSeek Key 接入、三篇小样本试跑与剩余外部配置。
- `docs/COMPATIBLE_API.md`：当前第三方接口、Key 变量、20M Token 配额与真实验收。
- `contracts/openapi.json`、`contracts/types.ts`、`contracts/api.ts`：前端契约与客户端。

## 云端组成

Supabase 提供 PostgreSQL、pgvector、Auth；Render 在新加坡通过 `Dockerfile.web` 同时运行
Next.js 前端和私有 FastAPI，并通过 `/api` 转发；GitHub 存放代码、运行 CI 和定时 Worker。
`render.web.yaml` 记录当前免费试运行方案；`render.yaml` 保留独立 API 的付费部署选项。
所有持久数据放 PostgreSQL，代码和测试副本留在 D 盘，密钥仅放云端 Secrets。

## 个人方向日报

支持按个人关键词检索、设置每日 1–50 篇、调节顶会/最新论文比例。
在日报页点击「立即生成日报」即可提交后台生成任务，完成后自动刷新；定时日报也复用保存的偏好。
选文口径、来源不足提示、任务恢复及部署迁移见 [个人日报说明](docs/PERSONAL_DAILY.md)。

## 开发命令

要求 Python 3.12+；生产数据库必须为 PostgreSQL + pgvector。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
# 将 .env.example 复制为 .env，填写数据库与 Supabase 信息
copilot migrate
copilot bootstrap --name "研究组" --admin-id SUPABASE_USER_UUID --admin-email ADMIN_EMAIL
uvicorn copilot.api:app --host 0.0.0.0 --port 8000
copilot daily --limit 200
copilot daily --use-cache --limit 5
copilot weekly
copilot doctor
pytest -q
```

不想本地运行时，在 Render Shell / GitHub Codespaces 运行同样的命令即可。
API 文档在 `/docs`，健康检查 `/healthz`，数据库就绪检查 `/readyz`。
`LLM_ENABLED=false` 默认只进行元数据和关键词模式，不会伪造 AI 报告。
`--use-cache` 仅关闭公共论文源网络请求；如启用 LLM，仍可发生有预算保护的模型调用。

## 数据源与实现依据

- [arXiv API](https://info.arxiv.org/help/api/user-manual.html)：`published` 为 v1 提交时间。
- [Supabase JWT](https://supabase.com/docs/guides/auth/jwts)：JWKS + issuer/audience 验签。
- [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)：
  Pydantic schema 输出，并处理拒答与不完整响应。
- [Render Blueprint](https://render.com/docs/blueprint-spec)：Docker 服务和迁移命令。

固定依赖写在 `requirements.lock`；Windows 验证环境为 Python 3.13，Linux CI 使用 Python 3.12。
