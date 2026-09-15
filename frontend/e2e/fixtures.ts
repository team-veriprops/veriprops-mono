/**
 * The suite's Playwright fixtures — import `test`/`expect` from here, not from `@playwright/test`.
 *
 * Each fixture replaces per-spec boilerplate a scenario would otherwise repeat:
 * - **Persona pages** (`customerPage`, `adminPage`, `opsAdminPage`, `financeAdminPage`,
 *   `agentPage(role)`, `anonPage`) open a context per persona from the session `globalSetup`
 *   captured, so one test can drive several personas side by side.
 * - **`scenario(stage)` / `pageFor(account)`** build an isolated case (`/dev/scenario`) and sign
 *   its fresh accounts in, which is what makes a spec safe to run in parallel.
 * - **`sweep(name)`, `wa`, `mail`** trigger the time-based jobs, the WhatsApp stub transport and
 *   the Mailpit inbox as preconditions. Business outcomes are still asserted in the browser.
 *
 * Every context is closed when the test ends. Fixture bodies name Playwright's hand-over
 * callback `provide` (not the conventional `use`) so React's hook lint rules don't mistake it
 * for a hook.
 */
import { Browser, BrowserContext, Page, test as base } from "@playwright/test";

import { AgentRole } from "@/types/agent";
import { HandoffIntent } from "@/types/handoff";
import { VerificationTier } from "@/types/verification";

import { anonymousApi, api } from "./helpers/api";
import { loginViaUi } from "./helpers/auth";
import { clearMailbox, extractLinkFromEmail, waitForEmail } from "./helpers/mailpit";
import { AGENT_PERSONA_BY_ROLE, Persona, PERSONAS, storageStatePath } from "./helpers/personas";
import { buildScenario, Scenario, ScenarioAccount, ScenarioOptions, ScenarioStage } from "./helpers/scenario";
import { readSeed } from "./helpers/seed";

export { expect } from "@playwright/test";

/** The time-based jobs a spec can trigger instead of waiting for their schedule. */
export enum Sweep {
  NO_SHOW = "NO_SHOW",
  POOL_STARVATION = "POOL_STARVATION",
  SLA_BREACH = "SLA_BREACH",
  ABANDONMENT = "ABANDONMENT",
  REFERRAL_CREDITS = "REFERRAL_CREDITS",
  COMMISSION_CLEARANCE = "COMMISSION_CLEARANCE",
  MESSAGE_RETRIES = "MESSAGE_RETRIES",
  SCHEDULED_BROADCASTS = "SCHEDULED_BROADCASTS",
}

const SWEEP_PATHS: Record<Sweep, string> = {
  [Sweep.NO_SHOW]: "/admin/verifications/sweeps/no-show",
  [Sweep.POOL_STARVATION]: "/admin/verifications/sweeps/pool-starvation",
  [Sweep.SLA_BREACH]: "/admin/verifications/sweeps/sla-breach",
  [Sweep.ABANDONMENT]: "/admin/verifications/sweeps/abandonment",
  [Sweep.REFERRAL_CREDITS]: "/admin/verifications/sweeps/referral-credits",
  [Sweep.COMMISSION_CLEARANCE]: "/admin/payouts/sweeps/commission-clearance",
  [Sweep.MESSAGE_RETRIES]: "/messages/sweeps/retries",
  [Sweep.SCHEDULED_BROADCASTS]: "/admin/broadcasts/sweeps/scheduled",
};

/** An inbound WhatsApp message injected into the real ingestion path. */
export interface WaInbound {
  fromPhone: string;
  text?: string;
  kind?: string;
  wamid?: string;
  senderName?: string;
  interactiveId?: string;
}

/** The WhatsApp stub transport's dev contract (backend `/dev/whatsapp/*`). */
export interface WaDriver {
  inbound(message: WaInbound): Promise<unknown>;
  outbox<T = unknown>(recipient?: string): Promise<T>;
  clearOutbox(): Promise<void>;
  /** Age a number's inbound journal so Meta's 24-hour service window reads as closed. */
  rewindWindow(phone: string, hours?: number): Promise<void>;
  mintHandoff(caseId: string, customerId: string, intent: HandoffIntent): Promise<string>;
}

export interface MailDriver {
  clear: typeof clearMailbox;
  waitFor: typeof waitForEmail;
  link: typeof extractLinkFromEmail;
}

type ScenarioBuilder = (
  stage: ScenarioStage,
  options?: ScenarioOptions & { tier?: VerificationTier },
) => Promise<Scenario>;

interface UatFixtures {
  /** A page signed in as a seeded persona (from its captured session). */
  pageAs: (persona: Persona) => Promise<Page>;
  /** A page signed in as any account through the real login form (e.g. a scenario's). */
  pageFor: (account: ScenarioAccount) => Promise<Page>;
  customerPage: Page;
  adminPage: Page;
  opsAdminPage: Page;
  financeAdminPage: Page;
  anonPage: Page;
  agentPage: (role: AgentRole) => Promise<Page>;
  scenario: ScenarioBuilder;
  sweep: (name: Sweep) => Promise<unknown>;
  wa: WaDriver;
  mail: MailDriver;
}

/**
 * Open a page in a new context, tracked for teardown. Contexts created from the `browser`
 * fixture inherit the project's `use` options (device, base URL, TLS handling).
 */
async function openPage(
  browser: Browser,
  contexts: BrowserContext[],
  storageState?: string,
): Promise<Page> {
  const context = await browser.newContext(storageState ? { storageState } : {});
  contexts.push(context);
  return context.newPage();
}

async function closeAll(contexts: BrowserContext[]): Promise<void> {
  await Promise.all(contexts.map((context) => context.close()));
}

export const test = base.extend<UatFixtures>({
  pageAs: async ({ browser }, provide) => {
    const contexts: BrowserContext[] = [];
    await provide((persona) => openPage(browser, contexts, storageStatePath(persona)));
    await closeAll(contexts);
  },

  pageFor: async ({ browser }, provide) => {
    const contexts: BrowserContext[] = [];
    await provide(async (account) => {
      const page = await openPage(browser, contexts);
      await loginViaUi(page, account.email, account.password);
      return page;
    });
    await closeAll(contexts);
  },

  customerPage: async ({ pageAs }, provide) => provide(await pageAs(PERSONAS.CUSTOMER)),
  adminPage: async ({ pageAs }, provide) => provide(await pageAs(PERSONAS.ADMIN)),
  opsAdminPage: async ({ pageAs }, provide) => provide(await pageAs(PERSONAS.ADMIN_OPERATIONS)),
  financeAdminPage: async ({ pageAs }, provide) => provide(await pageAs(PERSONAS.ADMIN_FINANCE)),

  anonPage: async ({ browser }, provide) => {
    const contexts: BrowserContext[] = [];
    await provide(await openPage(browser, contexts));
    await closeAll(contexts);
  },

  agentPage: async ({ pageAs }, provide) => {
    await provide((role) => pageAs(AGENT_PERSONA_BY_ROLE[role]));
  },

  scenario: async ({}, provide) => {
    await provide((stage, options = {}) => {
      const { tier = VerificationTier.STANDARD, ...scenarioOptions } = options;
      return buildScenario(stage, tier, scenarioOptions);
    });
  },

  sweep: async ({}, provide) => {
    // Sweeps are super-admin actions; the seed echoes that account's credentials.
    const { admin } = readSeed();
    const client = await api(admin.email, admin.password);
    await provide((name) => client.post(SWEEP_PATHS[name]));
    await client.dispose();
  },

  wa: async ({}, provide) => {
    const dev = await anonymousApi();
    await provide({
      inbound: (message) => dev.post("/dev/whatsapp/inbound", message),
      outbox: (recipient) => dev.get("/dev/whatsapp/outbox", recipient ? { recipient } : undefined),
      clearOutbox: async () => {
        await dev.delete("/dev/whatsapp/outbox");
      },
      rewindWindow: async (phone, hours = 25) => {
        await dev.post(
          `/dev/whatsapp/rewind-window?phone=${encodeURIComponent(phone)}&hours=${hours}`,
        );
      },
      mintHandoff: async (caseId, customerId, intent) =>
        (await dev.post<{ token: string }>("/dev/whatsapp/handoff-token", {
          caseId,
          customerId,
          intent,
        })).token,
    });
    await dev.dispose();
  },

  mail: async ({}, provide) => {
    await provide({ clear: clearMailbox, waitFor: waitForEmail, link: extractLinkFromEmail });
  },
});
