/**
 * Shape of the `/dev/seed` payload (backend `DevSeedService.seed`) plus the accessors
 * specs use to reach the seeded scenario.
 *
 * `globalSetup` performs the single reset+seed for a run (docs/uat-strategy.md §3) and
 * writes the payload to `SEED_STATE_FILE`; specs read it through `readSeed()` rather than
 * re-seeding, so the deterministic baseline is shared and a run stays reproducible.
 */
import { readFileSync } from "node:fs";

import { SEED_STATE_FILE } from "./env";

export interface SeededAccount {
  id: string;
  email: string;
  password: string;
}

export interface SeedPayload {
  /** The primary seeded customer (`qa-customer@veriprops.io`). */
  customer: SeededAccount;
  /** A disposable customer reserved for the NDPA-erasure scenarios (§19). */
  erasable: SeededAccount;
  /** Super-admin credentials, echoed from the backend's own settings. */
  admin: { email: string; password: string };
  /** Agent user ids keyed by `AgentRole` value (REGISTRY/FIELD/SURVEYOR/LAWYER). */
  agents: Record<string, string>;
  /** The primary verification: UNDER_REVIEW, SLA-overdue, all tasks review-approved. */
  verification: { id: string; vid: string; status: string };
  /** Primary-verification task ids keyed by role. */
  tasks: Record<string, string>;
  /** The "ops" verification (IN_PROGRESS) crafted for no-show / starvation / decline. */
  ops: { id: string; vid: string; txRef: string; tasks: Record<string, string> };
}

/** The seed payload captured by `globalSetup` for this run. */
export function readSeed(): SeedPayload {
  return JSON.parse(readFileSync(SEED_STATE_FILE, "utf-8")) as SeedPayload;
}

/** Email of a seeded agent by role — the accounts `seed()` creates per `AgentRole`. */
export function agentEmail(role: string): string {
  return `qa-agent-${role.toLowerCase()}@veriprops.io`;
}
