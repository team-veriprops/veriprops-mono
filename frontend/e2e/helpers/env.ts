/**
 * Runtime knobs for the UAT suite (docs/uat-strategy.md §9).
 *
 * Every value has a local-stack default so `pnpm e2e` works with no env setup; CI or a
 * developer pointing at a different stack overrides via the environment.
 */

/**
 * The Next.js app under test. Every request — including `/api/*` — goes through it,
 * because the backend is only ever reached via the Next proxy (root CLAUDE.md).
 *
 * **HTTPS by default, and that is load-bearing.** The session cookies are `__Host-`
 * prefixed, which requires the `Secure` attribute. Chromium treats `http://localhost` as a
 * secure context and keeps such cookies, but **WebKit does not** — over plain http it
 * silently drops all four, so every authenticated scenario fails on Safari for a reason
 * that would never occur in production (where traffic is HTTPS behind Cloudflare). Serving
 * the suite over TLS removes that false failure. Run the dev server with
 * `pnpm dev:https` (`next dev --experimental-https`).
 */
export const BASE_URL = process.env.UAT_BASE_URL ?? "https://localhost:3000";

/** API prefix on the frontend origin; the proxy rewrites it to the backend. */
export const API_PREFIX = process.env.NEXT_PUBLIC_API_PREFIX ?? "/api";

/** Mailpit's REST API — the only inbox the suite reads (invites, resets, share links). */
export const MAILPIT_URL = process.env.UAT_MAILPIT_URL ?? "http://localhost:8025";

/** Deterministic OTP: every OTP field in every flow takes this literal when the backend
 *  runs `OTP_MODE=deterministic`. The suite never reads an inbox for a code. */
export const TEST_OTP = "654123";

/** The password `/dev/seed` assigns to every seeded account. */
export const QA_PASSWORD = "Test1234!";

/* Consent versions are deliberately NOT pinned here. They differ per document type and move
 * independently — migration 0011 took PLATFORM_TERMS, PRIVACY_POLICY and
 * COMMUNICATION_RECORDING to 1.1.0 while the rest stayed at 1.0.0 — so any literal is wrong
 * for some document the day it is written. `/dev/seed` accepts the current version of every
 * required consent on each persona's behalf, which is why no spec needs one. A spec that
 * genuinely does must read it from `GET /users/auth/consents/documents` (public, returns
 * `type` + `consentVersion` per document), never restate it. */

/* Super-admin credentials are NOT configured here: `/dev/seed` echoes the backend's own
 * `SUPER_ADMIN_EMAIL`/`_PASSWORD` in its response payload, so the suite reads them from the
 * seed result (see `SeedPayload.admin`) and can never drift from the running backend. */

/** Where `globalSetup` parks per-persona `storageState` files. */
export const AUTH_STATE_DIR = "e2e/.auth";

/** Where `globalSetup` publishes the run-scoped seed payload for specs to consume. */
export const SEED_STATE_FILE = "e2e/.auth/seed.json";
