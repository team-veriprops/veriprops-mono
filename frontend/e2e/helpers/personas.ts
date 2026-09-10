/**
 * The personas the suite drives, and where their `storageState` lives.
 *
 * `globalSetup` logs each one in exactly once and persists its session, so specs start
 * already authenticated (docs/uat-strategy.md §3 step 2). Credentials come from the
 * `/dev/seed` payload — never hardcoded here — so they can't drift from the backend.
 */
import { AUTH_STATE_DIR } from "./env";

export const PERSONAS = {
  CUSTOMER: "customer",
  ERASABLE: "erasable",
  ADMIN: "admin",
  AGENT_REGISTRY: "agent-registry",
  AGENT_FIELD: "agent-field",
  AGENT_SURVEYOR: "agent-surveyor",
  AGENT_LAWYER: "agent-lawyer",
} as const;

export type Persona = (typeof PERSONAS)[keyof typeof PERSONAS];

/** The saved-session file for *persona*, used as a project/test `storageState`. */
export function storageStatePath(persona: Persona): string {
  return `${AUTH_STATE_DIR}/${persona}.json`;
}

/** Agent personas keyed by the `AgentRole` value the backend uses. */
export const AGENT_PERSONA_BY_ROLE: Record<string, Persona> = {
  REGISTRY: PERSONAS.AGENT_REGISTRY,
  FIELD: PERSONAS.AGENT_FIELD,
  SURVEYOR: PERSONAS.AGENT_SURVEYOR,
  LAWYER: PERSONAS.AGENT_LAWYER,
};
