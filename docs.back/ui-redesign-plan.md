# UI/UX Audit & Redesign Plan (Batch F)

Produced from a live Playwright walkthrough of the running app (frontend `:3000`, backend
`:8000`, seeded data). Scope decision: **audit-and-plan first, no code**; first redesign
surface is the **customer submission wizard**. This document is the roadmap for the
surface-by-surface redesign that follows.

## TL;DR

The **public surfaces are already premium** and should be left largely alone. The
**authenticated app (customer / agent / admin portals) is functional but visually plain** —
stock inputs, native radios, outlined cards, sparse layouts, and a few real correctness
bugs. The redesign is about lifting the portals to the same custom, mobile-first quality as
the marketing site, reusing the existing component library rather than starting over.

## Current-state findings (by surface, severity in brackets)

### Already strong — do not redesign
- **Marketing home** (`/`) — distinctive hero, editorial "why we exist", methodology,
  trust-score card. Premium. Preserve (see memory `project_home_page`, `project_seo_first_class`).
- **Auth login/signup** (`/auth/*`) — split brand panel + form, Google OAuth, trust signals.
  Premium. Preserve `data-testid` contracts.

### Customer submission wizard — PRIORITY (`app/portal/verifications/new`, `components/portal/submission/*`)
- **[High] Opaque validation.** With property type, address, landmark and state all filled,
  the primary **Continue button stays disabled with no explanation** — no inline errors, no
  required-field affordance, no "what's missing" hint. A real user gets stuck. Likely a
  missing `place_id` (address not chosen from autocomplete) or unshown conditional detail
  fields. Fix: explicit required markers + inline validation + a disabled-reason tooltip.
- **[High] Autocomplete component exists but the step uses a plain text input.**
  `components/ui/form/address/AddressSearchForm.tsx` (geo autocomplete) and the backend
  `/verifications/geo/autocomplete` + `/geo/place/{id}` endpoints exist, but `PropertyStep`
  renders a plain "Start typing the property address" input. Wire the real autocomplete
  (+ optional static map preview of the resolved point).
- **[Med] Native radios for property type.** Land/Building are tiny native radios. Replace
  with large, icon-led **selectable cards** (better tap targets, more premium, mobile-first).
- **[Med] No conditional detail fields.** PRD §5.1 wants Land (size/use/survey status) vs
  Building (floors/age/occupancy/C-of-O) fields; none are shown. Add per-type field groups.
- **[Med] Sparse layout, no summary rail.** Desktop shows a narrow centered column with a
  large empty lower half. Add a persistent **summary / price rail** (tier, running price,
  what-happens-next) so the flow feels guided and the price is always visible.
- **[Low] Stepper is minimal.** Fine functionally; upgrade to show current-step context,
  a time estimate, and completed-step checks.

### Verification tracking (`app/portal/verifications/[id]`, tracking components)
- **[High] Progress bar renders full (100% green) while every task shows "In Progress".**
  Misleading — reads as "done". Bind the bar to the real derived progress (§2.6 formula).
- **[Med] Opens as a modal overlay on top of a greyed portal shell.** Awkward; make it a
  proper full detail page/route (the `DrawerRoutePage`/`WizardOverlay` pattern is fine for
  wizards but the tracking view should feel like a destination).
- **[Low] Generic bordered card stack.** Elevate to a cohesive timeline + evidence layout.

### Customer dashboard (`/portal/dashboard`)
- **[Low] Standard outlined stat cards.** Functional; reuse `StatCard` but give the portal a
  stronger visual identity (recent-activity timeline, next-action prompts).

### Admin "Mission Control" (`/admin/dashboard` + admin surfaces)
- **[High] Raw enum badge shown to admins** — `UNDER_REVIEW` (underscore) rendered verbatim.
  Introduce a shared `StatusBadge` that maps enum → humanized label + semantic color, used
  everywhere a status appears (admin + customer).
- **[Med] Plain KPI cards, lots of empty space.** Rich data, flat presentation. Add hierarchy
  (primary vs secondary KPIs), trend/spark context, and denser mission-control layout.
- **[Note] DataTables are server-driven** (`components/ui/table/DataTable.tsx`) — keep the
  data contract; restyle the presentation only.

### Cross-cutting
- The portals read as a "default UI kit" (outlined cards + native controls) that clashes with
  the premium public surfaces. A single **custom design system pass** fixes most of it at once.

## Design-system foundation (reuse + extend, don't restart)

Existing assets to build on: `src/styles/theme.css` (tokens), `components/ui/*`
(`StatCard`, `DataTable`, `wizard/WizardOverlay`, `form/*`, `verified_input/*`,
`AddressSearchForm`), and the `tailwind-design-system` skill.

New/upgraded shared primitives to introduce (each with tests, mobile-first, theme-aware):
- **`SelectableCard`** — radio/checkbox card (property type, tier, payment method).
- **`FieldGroup`** — label + control + inline error + required affordance + hint; the
  disabled-CTA reason surfaces here.
- **`GeoAutocomplete`** — thin wrapper over `AddressSearchForm` + resolved-point preview.
- **`StatusBadge`** — enum → {label, tone}; single source of humanized status copy.
- **`PriceSummaryRail`** — sticky summary used across the wizard.
- **`ProgressTimeline`** — derived-progress bar + per-task timeline (tracking + report).
- Restyled **KPI card** grid for admin mission-control.

## Redesign roadmap (priority order)

1. **Customer submission wizard** (chosen first) — full custom redesign: selectable cards,
   real geo-autocomplete, conditional detail fields, inline validation, sticky price rail,
   upgraded stepper. Ships the reusable primitives above.
2. **Verification tracking + final report** — fix progress binding, full-page detail,
   `ProgressTimeline`, evidence layout.
3. **Agent task console + evidence capture** — mobile-first field UX (not yet walked; audit
   during the pass).
4. **Admin control panel + review/release + DataTable restyle** — `StatusBadge` everywhere,
   KPI hierarchy, denser mission-control.
5. **Dashboards, notifications, chat** — identity + next-action polish.

Each surface: navigate → redesign → visual-verify with Playwright → component tests → review.

## Invariants to preserve (non-negotiable)
- Never remove `data-testid`s (`login-*`/`signup-*`/`verify-*`/`oauth-*`) or the
  `window.__app_ready__/__auth_snapshot__/__oauth_complete__/__TEST_MODE__` hooks; gate on
  `isAutomationEnvironment()`.
- `DataTable` stays fully server-driven (`page`/`query`/`orderBy` → backend); pagination is
  server-side; wrap hosting pages in `<Suspense>`.
- camelCase types, **no facts derived on the frontend** — humanized status labels are display
  mappings of backend enum values, not new truth.
- Mobile-first, responsive, theme-aware; no duplicate layout systems.

## Verification
Per surface: `pnpm test` (vitest, incl. new component tests) + `pnpm build` + lint clean, and
a Playwright before/after walkthrough of the redesigned flow against the running app.
