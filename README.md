# Team AI Research Copilot

团队共享论文解析、方向推荐、组会认领与立项灵感池的云端工作台，已集成 Next.js 前端。

在线应用：[AI Research Copilot](https://team-ai-research-copilot.onrender.com)。
源码：[fengjinghwng-dot/team-ai-research-copilot](https://github.com/fengjinghwng-dot/team-ai-research-copilot)。
[GitHub Actions](https://github.com/fengjinghwng-dot/team-ai-research-copilot/actions) 已在 PostgreSQL 17 上通过 47 项后端测试，另有 4 项浏览器流程与 4 项登录回调检查。

## 先读这些文件

- `docs/FRONTEND_HANDOFF.md`：直接交给前端 agent 的功能、路由、文件和交互要求。
- `docs/CLOUD_DEPLOY.md`：Supabase + Render + GitHub Actions 云端部署步骤与所需连接。
- `SPEC.md`：缓存边界、权限、评分、预算和验收标准。
- `docs/STATUS.md`：已验证内容与仍需真实账号验证的内容。
- `docs/TOMORROW.md`：DeepSeek Key 接入、三篇小样本试跑与剩余外部配置。
- `contracts/openapi.json`、`contracts/types.ts`、`contracts/api.ts`：前端契约与客户端。

## 云端组成

Supabase 提供 PostgreSQL、pgvector、Auth；Render 在新加坡通过 `Dockerfile.web` 同时运行
Next.js 前端和私有 FastAPI，并通过 `/api` 转发；GitHub 存放代码、运行 CI 和定时 Worker。
`render.web.yaml` 记录当前免费试运行方案；`render.yaml` 保留独立 API 的付费部署选项。
所有持久数据放 PostgreSQL，代码和测试副本留在 D 盘，密钥仅放云端 Secrets。

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
