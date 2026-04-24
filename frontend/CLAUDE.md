# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

@AGENTS.md

## Commands

```bash
pnpm install
pnpm dev        # Dev server on http://localhost:3000
pnpm build
pnpm start
```

`/api/*` requests are proxied to `http://localhost:8000/api/*` via `next.config.ts` rewrites.

---

## Architecture

### Stack

- **Next.js 16** (App Router) + **React 19** + **TypeScript**
- **TailwindCSS 4** + **Radix UI** for styling/components
- **Zustand 5** for global client state
- **TanStack Query 5** for server state / API caching
- **React Hook Form** + **Zod** for form validation

### Key Directories

- `src/app/` — Next.js App Router pages and layouts
- `src/components/` — Reusable, stateless UI components
- `src/containers/` — Page-level components with business logic
- `src/stores/` — Zustand stores (auth, UI)
- `src/lib/` — API client wrappers, config (`lib/config/server.ts`, `lib/config/public.ts`)
- `src/providers/` — React context providers
- `src/types/` — Shared TypeScript types

## Notes

1. Always use 'frontend-design' skill when doing all ui/ux tasks.
