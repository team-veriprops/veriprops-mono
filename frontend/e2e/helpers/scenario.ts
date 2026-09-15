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

/** Where a scenario leaves its verification; each stage includes every earlier one. */
export enum ScenarioStage {
  DRAFT = "DRAFT",
  SUBMITTED = "SUBMITTED",
  PAID = "PAID",
  ASSIGNED = "ASSIGNED",
  IN_PROGRESS = "IN_PROGRESS",
  UNDER_REVIEW = "UNDER_REVIEW",
  REVIEW_APPROVED = "REVIEW_APPROVED",
  RELEASED = "RELEASED",
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
}

/** Build an isolated verification at *stage*. */
export async function buildScenario(
  stage: ScenarioStage,
  tier: VerificationTier = VerificationTier.STANDARD,
): Promise<Scenario> {
  const dev = await anonymousApi();
  try {
    return await dev.post<Scenario>("/dev/scenario", { stage, tier });
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
