# 给前端 agent 的交接说明

Next.js + Tailwind 页面已集成并部署。后续视觉优化请在 `frontend/` 开发，
先复用 `contracts/api.ts` 和 `contracts/types.ts`，保留现有鉴权和真实数据接口。
无需重做抓取、LLM 分析、去重、预算账本或数据库访问。

## 页面和对应文件

下表为已存在的页面和组件；新增功能对应文件列在表后。

| 功能 | 建议前端文件 | 已实现的接口/配套文件 |
|---|---|---|
| Google OAuth 登录、回调、未加入团队提示 | `frontend/app/login/page.tsx`、`frontend/app/auth/callback/route.ts` | Supabase Auth；`GET /v1/me`；`copilot/auth.py` |
| 团队选择 | `frontend/app/teams/page.tsx` | `/v1/me` 的 memberships；`/v1/teams/{team_id}/config` |
| 今日日报：团队必看 / 个人推荐 / 探索标签 / 日期切换 | `frontend/app/teams/[teamId]/page.tsx` | `GET /v1/teams/{id}/daily?day=YYYY-MM-DD` |
| 论文详情：报告与团队讨论双栏、事实/推断/假设分区 | `frontend/app/teams/[teamId]/papers/[paperId]/page.tsx` | `GET .../papers/{paper_id}`；`contracts/types.ts` |
| 文本批注与回复、引用定位 | `frontend/components/AnnotationThread.tsx`、`EvidenceQuote.tsx` | `POST .../papers/{id}/annotations`；每条 evidence 的 anchor/quote |
| 选择组会日期后认领、释放认领、冲突提示 | `frontend/components/ClaimButton.tsx` | `POST .../papers/{id}/claims`、`DELETE .../claims/{id}` |
| 价值投票：+1 / 取消 / -1 | `frontend/components/PaperVote.tsx` | `PUT .../papers/{id}/vote`；个人状态在 detail.my_vote |
| 团队知识库：关键词分页 / 语义检索 | `frontend/app/teams/[teamId]/library/page.tsx` | `GET .../papers?q=&limit=&offset=`、`POST .../search?q=` |
| 灵感池：新建、从假设或批注转存、阶段切换、负责人 | `frontend/app/teams/[teamId]/ideas/page.tsx`、`IdeaComposer.tsx` | `GET/POST .../ideas`、`PATCH .../ideas/{id}` |
| 周会材料下载、跨论文趋势 | `frontend/app/teams/[teamId]/meetings/page.tsx` | `GET .../reading-list` 返回 Markdown；`GET .../weekly` |
| 个人兴趣与邮件订阅 | `frontend/app/teams/[teamId]/settings/page.tsx` | `PATCH .../profile` |
| 管理员：主线、团队 Token 配额、成员角色 | `frontend/app/teams/[teamId]/admin/page.tsx` | `GET/PUT .../config`、`GET/PUT .../members` |
| 管理员：预算与任务状态 | `frontend/components/UsagePanel.tsx` | `GET .../admin/usage`、`GET .../admin/jobs` |
| API 与 Supabase 浏览器/服务端初始化 | `frontend/lib/api.ts`、`frontend/lib/supabase/client.ts`、`server.ts` | `contracts/api.ts`、`frontend/.env.example` |

新增组件：`PersonalReading.tsx` 提供收藏、已读与私有笔记；知识库支持收藏/未读筛选。
`MemberManager.tsx` 提供邮箱预授权邀请、撤销、角色调整和移出成员，不再要求填写 UUID。
`UsagePanel.tsx` 提供接入状态、全项目预算、费用估算上界和任务记录。
邀请不自动发邮件；对方用匹配的已验证邮箱登录并调用 `/v1/me` 后，以普通成员身份加入。

## 契约与鉴权

- 请求参数及错误结构：`contracts/openapi.json`，运行时 Swagger 在 API 的 `/docs`。
- 响应结构：`contracts/types.ts`。当前 OpenAPI 主要约束请求，部分动态响应未内联 Schema；
  以此 TypeScript 文件与 `copilot/api.py` 为响应依据，不要凭空补字段。
- 所有业务 API 都需要 `Authorization: Bearer <Supabase access_token>`。
- 使用 `@supabase/ssr` 的标准 PKCE 登录/回调；开启 Google provider 后即可接入。
- 不手写密码系统、不把用户在前端选择的 role 当权限依据、不使用 service-role key。
- 用户先调用 `/v1/me` 建立后台 profile 并接受未过期的邮箱邀请；没有 memberships 时显示等待邀请。
- 浏览器配置只有 API 地址、Supabase URL、公开 publishable key；服务端密钥不进前端。
- `createCopilotClient()` 接收异步 token getter，支持自动刷新后的 token。SSR 转发当前会话。

## 必须实现的真实状态

1. `analysis_state=metadata_only` 或 `analyses=[]`：显示摘要与“尚无 AI 解读”，不能造报告。
2. `source.kind=abstract`：显示“仅基于摘要”；`source.truncated=true`：显示“全文节选”。
3. `paper_facts`、`critical_gaps.kind`、`testable_hypotheses` 分开展示，假设标明待验证。
   每条 evidence 展示原句；HTML 使用 `source_url` 对应 `/html/{version}#anchor` 链接，
   PDF 使用 `https://arxiv.org/pdf/{version}#page=N`；LaTeX 文件锚点只显示来源名。
4. 日报未生成：`persisted=false`、列表为空，显示等待流水线；不要触发浏览器端 LLM。
5. 探索位按 `is_exploration` 呈现；实际比例取 actual/列表长度，不能固定宣称每天达到 20%。
6. 认领返回 409：刷新详情并显示已有分享人；重复本人认领为幂等成功。
7. 401 刷新会话/登录，403 显示无权限，404 显示当前团队不存在该项，422 显示字段错误；
   语义搜索 503 时提供关键词检索入口。错误体为 `{detail: string | validation_errors[]}`。
8. 批注、论文文本按纯文本渲染；若引入 Markdown，禁用原始 HTML 并过滤不安全链接。
9. 保存投票或认领后刷新论文状态；推荐排序在下一轮日报生成时更新。
10. IM 卡片链接直接进入详情页。未登录先登录并保留受信任站内 returnTo，随后用户认领。
11. 日报 `analysis_stale=true` 或报告的 `source.paper_version` 与论文 `arxiv_version` 不同：
    显示“旧版本报告”；详情页可查看历史报告，但不能当成新版本的分析结果。

## 数据与验收

正式应用已部署到 `https://team-ai-research-copilot.onrender.com`，API base 为同源 `/api`。
已有真实论文元数据，当前模型解读关闭；Supabase Auth 使用邮箱入口，SMTP 和中文模板已配置。
前端已集成并通过构建，线上 `NEXT_PUBLIC_USE_MOCK=false`；独立 Mock 只用于本地演示。
首位管理员已配置。浏览器交互检查使用明确标记的独立 Mock；权限和私有数据隔离另有真实 PostgreSQL 测试。
两位实际团队成员的线上浏览器验收仍待完成。
不要在业务代码里硬编码 team UUID、user UUID、论文 UUID 或管理员邮箱。

前端冒烟流程：登录 → 选团队 → 日报 → 论文详情 → 投票 → 认领 → 回复批注 →
假设转 Idea → 知识库搜索 → Markdown 导出 → 普通成员看不到管理入口且 API 仍拒绝。
完成后设置后端 `CORS_ORIGINS` 和 `WORKSPACE_URL` 为实际前端域名。
