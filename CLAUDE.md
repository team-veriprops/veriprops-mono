# CLAUDE.md - Real Estate Property Verification

Root-level guide for agents working on this repository. For full product requirements see [PRD.md](./PRD.md).

## Project Overview

Veriprops is a property verification and management platform. The repo is a monorepo with a FastAPI backend (`backend/`) and a Next.js frontend (`frontend/`).

See [backend/CLAUDE.md](backend/CLAUDE.md) for backend-specific guidance and [frontend/CLAUDE.md](frontend/CLAUDE.md) for frontend-specific guidance.

## How to Run

**Full stack (recommended):**
```bash
docker-compose up
```

**Backend only:**
```bash
cd backend
uvicorn veriprops:app --reload
```

**Frontend only:**
```bash
cd frontend
pnpm dev
```


## Reference Docs

- **[PRD.md](./PRD.md)** — Full product requirements.
- **[backend/CLAUDE.md](./backend/CLAUDE.md)** — for backend-specific guidance.
- **[frontend/CLAUDE.md](./frontend/CLAUDE.md)** — for frontend-specific guidance.



## Workflow for new Features
1. Write a plan and confirm with user before coding.
2. Write tests first (Test Driven Development - TDD).
3. Implement the Feature.
4. Run test and confirm all passing.
5. Update the appropriate CLAUDE.md if new patterns emerge.

## Notes

1. Always use 'test-driven-development' skill when making changes, and observe the following:
1.1. Adapt all npm to pnpm
1.2. Write jest and pytest tests based on their best practices.
