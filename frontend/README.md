# Frontend workspace reserved for the UI agent

请先读 `../docs/FRONTEND_HANDOFF.md`。Next.js UI、组件和样式都放此目录。
复用 `../contracts/api.ts` 和 `../contracts/types.ts`；不要复制后端或实现第二套分析服务。
本次后端交付不生成页面视觉设计。`/auth/callback` 和 Google OAuth PKCE 回调由前端实现。
