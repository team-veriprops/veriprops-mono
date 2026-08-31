/**
 * One reset + seed per run, then one login per persona (docs/uat-strategy.md §3).
 *
 * This establishes the deterministic baseline the whole suite shares and makes a full run
 * reproducible from a clean database. It is a *fast default*, not a dependency chain:
 * specs needing a precondition the seed lacks bootstrap it themselves via the API helper,
 * so any spec can still run alone under `--grep`.
 */
import { mkdirSync, writeFileSync } from "node:fs";

import { chromium } from "@playwright/test";

import { anonymousApi } from "./helpers/api";
import { loginViaUi } from "./helpers/auth";
import { AUTH_STATE_DIR, BASE_URL, QA_PASSWORD, SEED_STATE_FILE } from "./helpers/env";
import { AGENT_PERSONA_BY_ROLE, Persona, PERSONAS, storageStatePath } from "./helpers/personas";
import { SeedPayload, agentEmail } from "./helpers/seed";

export default async function globalSetup(): Promise<void> {
  mkdirSync(AUTH_STATE_DIR, { recursive: true });

  const seed = await resetAndSeed();
  writeFileSync(SEED_STATE_FILE, JSON.stringify(seed, null, 2), "utf-8");

  await captureSessions(seed);
}

/** Clear domain data and rebuild the deterministic scenario. */
async function resetAndSeed(): Promise<SeedPayload> {
  const dev = await anonymousApi();
  try {
    await dev.post("/dev/reset");
    return await dev.post<SeedPayload>("/dev/seed");
  } finally {
    await dev.dispose();
  }
}

/**
 * Log every persona in through the real login form and persist its `storageState`.
 *
 * UI login (rather than an API call) is deliberate: it captures the localStorage mirror
 * the app writes alongside the session cookies, so a spec resuming from the saved state
 * lands in exactly the state a real returning user would.
 */
async function captureSessions(seed: SeedPayload): Promise<void> {
  const credentials: [Persona, string, string][] = [
    [PERSONAS.CUSTOMER, seed.customer.email, seed.customer.password],
    [PERSONAS.ERASABLE, seed.erasable.email, seed.erasable.password],
    [PERSONAS.ADMIN, seed.admin.email, seed.admin.password],
    ...Object.entries(AGENT_PERSONA_BY_ROLE)
      .filter(([role]) => role in seed.agents)
      // Seeded agents all share the QA password; the seed payload returns only their ids.
      .map(([role, persona]): [Persona, string, string] => [
        persona,
        agentEmail(role),
        QA_PASSWORD,
      ]),
  ];

  const browser = await chromium.launch();
  try {
    for (const [persona, email, password] of credentials) {
      const context = await browser.newContext({ baseURL: BASE_URL, ignoreHTTPSErrors: true });
      const page = await context.newPage();
      await loginViaUi(page, email, password);
      await context.storageState({ path: storageStatePath(persona) });
      await context.close();
    }
  } finally {
    await browser.close();
  }
}
