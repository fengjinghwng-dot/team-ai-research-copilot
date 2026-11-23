# Coding instructions

- This is the backend for a team product. Preserve PostgreSQL + pgvector, shared analysis caches,
  and explicit team membership checks. Never add SQLite or development auth bypasses.
- Frontend work belongs under `frontend/`. Read `docs/FRONTEND_HANDOFF.md` and `contracts/` first.
  Do not change backend payloads to fit a mock UI without updating contracts and checks.
- Public paper metadata, source documents, and neutral reports may be shared. Team discussions,
  personal preferences, claims, ideas, digests and budget data must always be team scoped.
- Keep prompts in `copilot/prompts/`. Every changed prompt changes the cache fingerprint.
- Fetch public source data through `Fetcher`; use `--use-cache` during parsing/prompt iteration.
  Never cache access tokens, OAuth responses, webhook credentials or API keys.
- All LLM/embedding calls must reserve budget before I/O, use structured schemas, and settle usage.
  Never add implicit retries to paid calls. Unknown charge outcomes keep their reservation.
- Evidence quotes and anchors must pass validation before a report is stored. Never fabricate
  gold-set scores, real paper evaluation, benchmark results, provider confirmations or deployment state.
- Add focused smoke checks for meaningful module changes. Run `ruff check .`, `pytest -q`, and
  the PostgreSQL checks when changing persistence. CI must run migrations twice (idempotency).
- Applied SQL migrations are immutable. Add a numbered migration instead of editing an applied one.
- Do not commit `.env`, API credentials, private research text, user emails or local caches.
- Use cloud secret managers/GitHub Secrets for credentials. Keep all task-generated local files on D:.
