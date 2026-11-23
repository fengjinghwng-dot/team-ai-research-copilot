# Team AI Research Copilot — Frontend (`frontend/`)

本代码包严格依据仓库 `docs/FRONTEND_HANDOFF.md`、`contracts/types.ts` 和 `contracts/api.ts` 生成，采用 Next.js App Router + Tailwind CSS + `@supabase/ssr`。

## 1. 放进仓库的方法
将解压后的整个 `frontend/` 目录直接放到你的仓库 `team-ai-research-copilot/frontend/` 下（覆盖或合并 `.env.example`）。

## 2. 本地启动（两种模式）

### A. 独立 Mock 演示模式（无需后端和 Supabase 即可先看完整界面）
```bash
cd frontend
cp .env.example .env.local
# 在 .env.local 中将 NEXT_PUBLIC_USE_MOCK 改为 true
npm install
npm run dev
```
打开 `http://localhost:3000` 即可体验完整页面，顶部黄色横幅支持一键切换 `admin` / `member` 角色验证权限隔离。

### B. 正式联调与上线（Vercel 部署）
1. 在 `.env.local` 或 Vercel 环境变量中填入真实值，并确保 `NEXT_PUBLIC_USE_MOCK=false`：
   - `NEXT_PUBLIC_API_BASE_URL`
   - `NEXT_PUBLIC_SUPABASE_URL`
   - `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`
2. 在 Supabase 控制台 Authentication -> URL Configuration 中，将 `https://你的前端域名/auth/callback` 加入 Redirect URLs，并开启 Google Provider。
3. 在后端环境变量中将 `CORS_ORIGINS` 和 `WORKSPACE_URL` 设置为你的实际前端域名。
4. 用至少两个账号（1 个 `admin`、1 个 `member`）跑通冒烟流程：登录 -> 选团队 -> 日报 -> 论文详情 -> 投票 -> 认领 -> 回复批注 -> 假设转 Idea -> 知识库搜索 -> Markdown 导出 -> 确认普通成员看不到管理入口且 API 返回 403。
