import { describe, it, expect } from "vitest";
import { AgentRole, CredentialType, KycMethod } from "@/types/agent";
import { EMPTY_WIZARD_STATE, AgentWizardState } from "./types";
import { canAdvanceStep, canSubmit } from "./validation";

const withState = (patch: Partial<AgentWizardState>): AgentWizardState => ({
  ...EMPTY_WIZARD_STATE,
  ...patch,
});

describe("canAdvanceStep", () => {
  it("blocks step 0 until a role is chosen", () => {
    expect(canAdvanceStep(0, withState({ roles: [] }))).toBe(false);
    expect(canAdvanceStep(0, withState({ roles: [AgentRole.FIELD] }))).toBe(true);
  });

  it("requires a BVN of sufficient length on the BVN path", () => {
    expect(canAdvanceStep(1, withState({ kyc: { method: KycMethod.BVN, bvn: "123" } }))).toBe(false);
    expect(canAdvanceStep(1, withState({ kyc: { method: KycMethod.BVN, bvn: "22222222222" } }))).toBe(true);
  });

  it("requires id type + number on the government-ID path", () => {
    expect(canAdvanceStep(1, withState({ kyc: { method: KycMethod.GOV_ID } }))).toBe(false);
    expect(
      canAdvanceStep(1, withState({ kyc: { method: KycMethod.GOV_ID, idType: "NIN" as never, idNumber: "5" } })),
    ).toBe(true);
  });

  it("requires a licence number for each credential-bearing role", () => {
    const missing = withState({
      credentials: [{ role: AgentRole.LAWYER, credentialType: CredentialType.NBA_LICENCE }],
    });
    expect(canAdvanceStep(2, missing)).toBe(false);
    const filled = withState({
      credentials: [
        { role: AgentRole.LAWYER, credentialType: CredentialType.NBA_LICENCE, licenceNumber: "NBA-1" },
      ],
    });
    expect(canAdvanceStep(2, filled)).toBe(true);
  });
});

describe("canSubmit", () => {
  it("requires truthfulness, terms, and at least one role", () => {
    const base = withState({ roles: [AgentRole.FIELD], truthfulnessConfirmed: true });
    expect(canSubmit(base, false)).toBe(false); // terms not accepted
    expect(canSubmit(withState({ roles: [AgentRole.FIELD] }), true)).toBe(false); // not truthful
    expect(canSubmit(base, true)).toBe(true);
  });
});
