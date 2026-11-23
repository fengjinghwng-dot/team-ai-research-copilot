# 交付状态 · 2026-11-23

## 已完成实现

- PostgreSQL 私有 schema、pgvector HNSW、19 张业务表、带校验和的幂等 SQL 迁移。
- Supabase 非对称 JWT 验签、团队角色、成员管理和 CLI 首位管理员初始化。
- arXiv/HF/S2 公共候选抓取、v1 首次提交校验、版本/DOI/保守标题去重和持久 HTTP 缓存。
- HTML → LaTeX → PDF 全文降级、锚点、解压/大小上限、截断标记。
- 外置 Prompt、Structured Outputs、精读/摘要解读、原文引用检查和全员共享解析缓存。
- 团队主线 + 个人兴趣 + 协作反馈排序、约 20% 探索位及实际比例报告。
- 论文库、关键词/向量检索、讨论串、认领与冲突处理、投票、Idea Backlog。
- 站内日报、每周 Reading List Markdown 导出与周五快照、周日跨论文聚类分析。
- 全球/团队 Token 账本预留、结算、未知收费状态保守处理与预算降级。
- 飞书/企微/Slack 群卡片、Resend 个人邮件适配器；默认不发送。
- Docker/Compose、Render Blueprint、GitHub CI 与定时任务文件；前端契约与交接文档。
- 已接入实际交付的 Next.js 前端、邮箱登录入口与北京时间日期显示。
- 新加坡 Supabase 数据库和 Render 全栈服务已创建；前端/API 共用一个 HTTPS 地址。

## 本次实际验证

日期：2026-11-23。Python 3.13，D 盘虚拟环境。

| 检查 | 实际结果 |
|---|---|
| Ruff 静态检查 | 通过 |
| Python 依赖完整性 `pip check` | 通过 |
| 单元 + 本地数据库集成 | **29 passed, 1 skipped** |
| GitHub Actions：Ubuntu + Python 3.12 + PostgreSQL 17 / pgvector | **30 passed, 0 skipped**；[已验证的 CI 运行](https://github.com/fengjinghwng-dot/team-ai-research-copilot/actions/runs/45148407203) |
| 初始迁移 + 完整性迁移 | 本地 PGlite/PostgreSQL WASM + pgvector 成功执行；再次执行无重复修改 |
| 团队隔离、越权、认领冲突、幂等投票、Idea 关联 | 通过 |
| 解析缓存跨读者复用、版本去重、预算顺序结算 | 通过，模型部分使用明确的测试替身 |
| TypeScript API 客户端 | `tsc --noEmit --strict` 通过 |
| 全栈容器与前端 CI | Linux Docker 构建和 Next.js 生产构建均通过；npm audit 为 0 项漏洞 |
| 真实 Supabase 数据库 | PostgreSQL 17.12，新加坡；业务表、pgvector 索引与权限迁移及幂等验证通过 |
| 线上页面与接口 | 浏览器中邮箱表单可见、0 个 JS 错误、无 Mock 横幅；healthz/readyz 返回 200，匿名 /me 返回 401 |
| arXiv API | HTTP 200，返回 2 篇且可提取首次提交时间 |
| HF Daily Papers | HTTP 200，返回 2 条 |
| Semantic Scholar bulk search | HTTP 200，返回 1000 条；业务仅处理有上限的候选 |
| 真实论文入库 | 首轮 60 篇通过首次提交时间校验，筛出 20 篇；Semantic Scholar 失败已回退并记录 warning |
| 用户邮件登录 / LLM / IM | SMTP 授权码、模型 API 与预算、IM 配置仍待补齐；未实际调用付费模型 |

跳过的用例是**双独立 PostgreSQL 后端的并发预算竞争**。PGlite 只有一个 WASM 后端，
不能据此证明真正的数据库并发隔离。随后 GitHub CI 已使用 `pgvector/pgvector:pg17`
实跑全部 30 项测试，包含双后端并发预算竞争，全部通过且无跳过。
测试中遇到 Starlette 对旧 httpx TestClient 的弃用提示，当前测试通过。

已实跑一次云端数据库入库；60 篇是本轮真实数量，没有承诺每天固定获得 100–200 篇。
未做 10 篇专家黄金集评分。引用字符串校验不能等同于已经解决 AI 幻觉。

## GitHub 和云端状态

仓库由用户改为**公开**以便前端协作，源码、前端、CI 和定时任务已推送：
`https://github.com/fengjinghwng-dot/team-ai-research-copilot`。
本地项目保留在 D 盘。用户已明确批准 GitHub CLI 的 workflow 权限，用于上传 Actions 文件。
已核对远程主分支与本地提交一致；真实 PostgreSQL CI 已通过。
正式地址：[AI Research Copilot](https://team-ai-research-copilot.onrender.com)。
API 前缀 `/api`，文档 `/api/docs`，健康检查 `/api/healthz`、`/api/readyz`。
Supabase 与 Render 都在新加坡；当前使用免费实例，Render 空闲休眠后的首次访问会有冷启动。
数据库凭据已按用户明确授权，存入 Render 环境变量与 GitHub Production Secrets。
已扫描跟踪文件，未发现本项目真实数据库密码、连接凭据或用户发信邮箱。
定时元数据流水线已开启：每日北京时间 08:30、周五 Reading List、周日趋势任务。
模型调用仍关闭，预算上限变量为 300000 tokens/天；模型与实际费用预算尚待用户确定。

下一步：SMTP 授权码保存与实际邮箱登录 → 为已验证的指定账号初始化管理员 →
模型 API / 预算与黄金集验收 → 启用结构化解读及向量检索。

## 明确的第一版边界

- 前端由另一个 agent 提供，已集成并完成生产构建和真实浏览器检查。
- 当前默认入口为 Supabase 邮箱登录；Google 为可选配置，飞书/企微尚未接入。
- IM“查看/认领”按钮进入工作台后操作；直接 IM 身份绑定认领尚未实现。
- 每部署一个群 webhook，并明确绑定 team_id；多个团队群的加密 integration 管理待扩展。
- 没有伪造黄金集、模拟论文日报冒充真实结果或承诺已测得的成本节省百分比。
