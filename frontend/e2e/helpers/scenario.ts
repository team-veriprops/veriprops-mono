/**
 * Lifecycle scenarios: a spec's precondition, built by the backend (`POST /dev/scenario`).
 *
 * A scenario is a verification already standing at a lifecycle stage, with **its own**
 * customer and **its own** approved agents. Every transition behind it ran through the real
 * backend services, so the state a spec starts from is what production would produce. And
 * because nothing is shared with other specs, scenario-based specs can run in parallel.
 *
 * Preconditions only: assert business outcomes in the browser, never through this client.
 */
import { AgentRole } from "@/types/agent";
import { VerificationStatus, VerificationTier } from "@/types/verification";

import { anonymousApi } from "./api";

/**
 * Where a scenario leaves its verification. Stages up to `RELEASED` are cumulative; the last
 * three are alternative branches off a released case — each includes `RELEASED`, never another
 * branch.
 */
export enum ScenarioStage {
  DRAFT = "DRAFT",
  SUBMITTED = "SUBMITTED",
  PAID = "PAID",
  ASSIGNED = "ASSIGNED",
  IN_PROGRESS = "IN_PROGRESS",
  UNDER_REVIEW = "UNDER_REVIEW",
  REVIEW_APPROVED = "REVIEW_APPROVED",
  RELEASED = "RELEASED",
  /** The customer disputed the released report (`disputeId` set). */
  DISPUTED = "DISPUTED",
  /** A re-check awaits the admin's decision (`recheckId` set). */
  RECHECK_REQUESTED = "RECHECK_REQUESTED",
  /** Commissions cleared: each agent has an available balance and a stored beneficiary. */
  PAYOUT_READY = "PAYOUT_READY",
}

/** A login-able participant; every scenario account shares the QA password. */
export interface ScenarioAccount {
  id: string;
  email: string;
  password: string;
}

export interface ScenarioAgent extends ScenarioAccount {
  /** The agent's task on this verification, once assigned (hex id, as the wire carries it). */
  taskId: string | null;
  /** `PAYOUT_READY` only: withdrawable balance in kobo. */
  availableMinor: number | null;
  /** `PAYOUT_READY` only: the stored beneficiary a payout can be requested into. */
  bankAccountId: string | null;
}

export interface Scenario {
  stage: ScenarioStage;
  verificationId: string;
  vid: string;
  status: VerificationStatus;
  tier: VerificationTier;
  customer: ScenarioAccount;
  /** One agent per role the tier requires. */
  agents: Partial<Record<AgentRole, ScenarioAgent>>;
  /** `DISPUTED` only. */
  disputeId: string | null;
  /** `RECHECK_REQUESTED` only. */
  recheckId: string | null;
}

export interface ScenarioOptions {
  /**
   * `false` leaves the customer at their first payment with an unverified phone, so a spec can
   * drive the pay-step phone gate (§10.5). Only valid for stages before `PAID`.
   */
  customerPhoneVerified?: boolean;
}

/** Build an isolated verification at *stage*. */
export async function buildScenario(
  stage: ScenarioStage,
  tier: VerificationTier = VerificationTier.STANDARD,
  options: ScenarioOptions = {},
): Promise<Scenario> {
  const dev = await anonymousApi();
  try {
    return await dev.post<Scenario>("/dev/scenario", { stage, tier, ...options });
  } finally {
    await dev.dispose();
  }
}

/** The scenario agent for *role*, failing loudly when the tier has no such role. */
export function scenarioAgent(scenario: Scenario, role: AgentRole): ScenarioAgent {
  const agent = scenario.agents[role];
  if (!agent) {
    throw new Error(`Scenario ${scenario.vid} (${scenario.tier}) has no ${role} agent`);
  }
  return agent;
}
