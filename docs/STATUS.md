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

## 本次实际验证

日期：2026-11-23。Python 3.13，D 盘虚拟环境。

| 检查 | 实际结果 |
|---|---|
| Ruff 静态检查 | 通过 |
| Python 依赖完整性 `pip check` | 通过 |
| 单元 + 本地数据库集成 | **29 passed, 1 skipped** |
| 初始迁移 + 完整性迁移 | 本地 PGlite/PostgreSQL WASM + pgvector 成功执行；再次执行无重复修改 |
| 团队隔离、越权、认领冲突、幂等投票、Idea 关联 | 通过 |
| 解析缓存跨读者复用、版本去重、预算顺序结算 | 通过，模型部分使用明确的测试替身 |
| TypeScript API 客户端 | `tsc --noEmit --strict` 通过 |
| Compose、Render、Actions YAML | 语法解析通过；未进行容器构建或平台端 Blueprint 校验 |
| arXiv API | HTTP 200，返回 2 篇且可提取首次提交时间 |
| HF Daily Papers | HTTP 200，返回 2 条 |
| Semantic Scholar bulk search | HTTP 200，返回 1000 条；业务仅处理有上限的候选 |
| 真实 LLM / SSO / IM / 邮件 | 未执行；缺少账号连接或 Secrets，未产生本次模型调用费用 |

跳过的用例是**双独立 PostgreSQL 后端的并发预算竞争**。PGlite 只有一个 WASM 后端，
不能据此证明真正的数据库并发隔离。CI 已使用 `pgvector/pgvector:pg17` 且不设置跳过变量；
推到 GitHub 后必须检查这项通过，才可将并发能力标为云端验收完成。
测试中遇到 Starlette 对旧 httpx TestClient 的弃用提示，当前测试通过。

公开源 smoke 只验证连通和响应格式，没有证明每天都能获得 100–200 篇符合团队画像的新论文。
未做 10 篇专家黄金集评分。引用字符串校验不能等同于已经解决 AI 幻觉。

## GitHub 和云端状态

用户已授权新建 **私有**仓库 `team-ai-research-copilot`。
本地仓库已初始化；远程仓库**尚未创建/推送**，当前未连接 GitHub，本机凭据管理器也无登录账号。
Supabase / Render 项目**尚未创建/部署**，没有已上线 API 地址。
定时流水线默认关闭，不会未经配置就运行抓取、发送消息或产生模型调用。

下一步：连接 GitHub → 创建私有仓库并推送 → 看真实 PostgreSQL CI → 连接 Supabase/Render →
迁移和首位管理员初始化 → 前端接入 SSO → 真实源/黄金集验收 → 低预算启用自动日报。

## 明确的第一版边界

- 前端页面、OAuth 回调 UI 由另一个 agent 制作；本项目只预留 `frontend/` 和交接文件。
- Google OAuth 配置方案已给出；飞书/企微 SSO 尚未做真实身份提供方接入。
- IM“查看/认领”按钮进入工作台后操作；直接 IM 身份绑定认领尚未实现。
- 每部署一个群 webhook，并明确绑定 team_id；多个团队群的加密 integration 管理待扩展。
- 没有伪造黄金集、模拟论文日报冒充真实结果或承诺已测得的成本节省百分比。
