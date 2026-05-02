# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Veriprops is a property verification platform. Monorepo with two deployable apps that talk over HTTP:

- [backend/](backend/) — FastAPI service (Python 3.12, MySQL, async SQLAlchemy, Alembic). See [backend/CLAUDE.md](backend/CLAUDE.md).
- [frontend/](frontend/) — Next.js 16 App Router, React 19, TypeScript. See [frontend/CLAUDE.md](frontend/CLAUDE.md).

Product context lives in [PRD.md](PRD.md) — read the relevant section before designing features that touch verification, agent onboarding, or reports.

## Running both ends

The frontend rewrites `/api/*` to the backend (see [frontend/next.config.ts](frontend/next.config.ts)), so for any feature that crosses the boundary, run both:

```bash
# terminal 1 — backend on :8000
cd backend && python veriprops.py

# terminal 2 — frontend on :3000
cd frontend && pnpm dev
```

Frontend reads `API_BASE_URL` (server-only) from its env to build the proxy target. If you change ports, update both ends.

## Cross-cutting conventions

- **API casing.** Backend Pydantic models serialize as camelCase (via `to_camel` alias generator in [appodus_utils/db/models.py](backend/main/appodus_utils/db/models.py)) but Python code stays snake_case. Frontend types are camelCase — don't add a transformation layer.
- **Auth contract.** The auth controller at [backend/main/app/domain/user/auth/controller.py](backend/main/app/domain/user/auth/controller.py) is the source of truth for endpoints the frontend's `auth-service.ts` ([frontend/src/components/website/auth/libs/auth-service.ts](frontend/src/components/website/auth/libs/auth-service.ts)) calls. URL shape is `/api/users/auth/...`. When adding/renaming an endpoint, change both files in the same PR.
- **Package managers.** Frontend is `pnpm` (lockfile committed); never use `npm` or `yarn`. Backend is plain `pip` against `requirements.txt`.
- **Path handling.** Memory rule: use `path.join` / `pathlib` / POSIX-safe APIs — never hardcode `\` or `/` separators.

## Workflow

When adding a feature, write a short plan and confirm with the user before coding, write tests first, then implement. Update the relevant `CLAUDE.md` if a new pattern emerges that future agents would otherwise have to re-derive.

### Non-negotiable rule
1. No Frontend/Backend duplicate implementations. 
2. As much as possible, deliver all implementation as full vertical slices (backend domains + Alembic migrations + tests + frontend ) so each phase ships demoably end-to-end.