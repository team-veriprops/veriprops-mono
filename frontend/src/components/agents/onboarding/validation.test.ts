import { describe, it, expect } from "vitest";
import { AgentRole, CredentialType, GovIdType, KycMethod } from "@/types/agent";
import { EMPTY_WIZARD_STATE, AgentWizardState, KycPhotos } from "./types";
import { canAdvanceStep, canSubmit, kycNeedsDocument, KycRules } from "./validation";

const withState = (patch: Partial<AgentWizardState>): AgentWizardState => ({
  ...EMPTY_WIZARD_STATE,
  ...patch,
});

// The backend names these in public config (the ones no provider matches on its own).
const DOCUMENT_TYPES = [GovIdType.PASSPORT, GovIdType.DRIVERS_LICENCE, GovIdType.VOTERS_CARD];
const rules = (photos: KycPhotos = { selfie: "/9j/selfie" }): KycRules => ({ photos, documentIdTypes: DOCUMENT_TYPES });

describe("canAdvanceStep", () => {
  it("blocks step 0 until a role is chosen", () => {
    expect(canAdvanceStep(0, withState({ roles: [] }), rules())).toBe(false);
    expect(canAdvanceStep(0, withState({ roles: [AgentRole.FIELD] }), rules())).toBe(true);
  });

  it("requires a BVN of sufficient length on the BVN path", () => {
    expect(canAdvanceStep(1, withState({ kyc: { method: KycMethod.BVN, bvn: "123" } }), rules())).toBe(false);
    expect(canAdvanceStep(1, withState({ kyc: { method: KycMethod.BVN, bvn: "22222222222" } }), rules())).toBe(true);
  });

  it("requires a selfie on every path", () => {
    const bvn = withState({ kyc: { method: KycMethod.BVN, bvn: "22222222222" } });
    expect(canAdvanceStep(1, bvn, rules({}))).toBe(false);
  });

  it("requires id type + number on the government-ID path", () => {
    expect(canAdvanceStep(1, withState({ kyc: { method: KycMethod.GOV_ID } }), rules())).toBe(false);
    expect(
      canAdvanceStep(1, withState({ kyc: { method: KycMethod.GOV_ID, idType: GovIdType.NIN, idNumber: "5" } }), rules()),
    ).toBe(true);
  });

  it("waits for the backend's rules before judging the identity step complete", () => {
    const passport = withState({ kyc: { method: KycMethod.GOV_ID, idType: GovIdType.PASSPORT, idNumber: "A0" } });
    expect(canAdvanceStep(1, passport, { photos: { selfie: "/9j/s" } })).toBe(false);
  });

  it("requires a photo of the document for the IDs a reviewer checks", () => {
    const passport = withState({ kyc: { method: KycMethod.GOV_ID, idType: GovIdType.PASSPORT, idNumber: "A0" } });
    expect(canAdvanceStep(1, passport, rules({ selfie: "/9j/s" }))).toBe(false);
    expect(canAdvanceStep(1, passport, rules({ selfie: "/9j/s", idDocument: "/9j/d" }))).toBe(true);
  });

  it("requires a licence number for each credential-bearing role", () => {
    const missing = withState({
      credentials: [{ role: AgentRole.LAWYER, credentialType: CredentialType.NBA_LICENCE }],
    });
    expect(canAdvanceStep(2, missing, rules())).toBe(false);
    const filled = withState({
      credentials: [
        { role: AgentRole.LAWYER, credentialType: CredentialType.NBA_LICENCE, licenceNumber: "NBA-1" },
      ],
    });
    expect(canAdvanceStep(2, filled, rules())).toBe(true);
  });
});

describe("kycNeedsDocument", () => {
  it("follows the backend's list, and only on the government-ID path", () => {
    expect(kycNeedsDocument({ method: KycMethod.GOV_ID, idType: GovIdType.VOTERS_CARD }, DOCUMENT_TYPES)).toBe(true);
    expect(kycNeedsDocument({ method: KycMethod.GOV_ID, idType: GovIdType.NIN }, DOCUMENT_TYPES)).toBe(false);
    expect(kycNeedsDocument({ method: KycMethod.BVN, idType: GovIdType.PASSPORT }, DOCUMENT_TYPES)).toBe(false);
  });
});

describe("canSubmit", () => {
  const complete = withState({
    roles: [AgentRole.FIELD], truthfulnessConfirmed: true, kyc: { method: KycMethod.BVN, bvn: "22222222222" },
  });

  it("requires truthfulness, terms, and at least one role", () => {
    expect(canSubmit(complete, false, rules())).toBe(false); // terms not accepted
    expect(canSubmit({ ...complete, truthfulnessConfirmed: false }, true, rules())).toBe(false);
    expect(canSubmit(complete, true, rules())).toBe(true);
  });

  it("requires the photos again after a resumed draft, which never kept them", () => {
    expect(canSubmit(complete, true, rules({}))).toBe(false);
  });
});
