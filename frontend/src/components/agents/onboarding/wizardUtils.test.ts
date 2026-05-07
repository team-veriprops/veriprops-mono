import { describe, it, expect } from "vitest";
import { deriveResumeStep, validateCredentialsStep } from "./wizardUtils";
import type { AgentApplication } from "../libs/agent-service";

const base: AgentApplication = {
  id: "app_1",
  userId: "u_1",
  status: "DRAFT",
  types: [],
  kycMethod: null,
  bvnLast4: null,
  bvnVerifiedAt: null,
  idDocType: null,
  idDocUploaded: false,
  selfieUploaded: false,
  selfieMatchScore: null,
  surveyorLicenceNo: null,
  nbaLicenceNo: null,
  yearsOfExperience: null,
  coverageStates: [],
  coverageLgas: [],
  bio: null,
  submittedAt: null,
  reviewedAt: null,
  rejectionReason: null,
  createdAt: "2026-05-07T00:00:00Z",
  updatedAt: null,
};

// ─── deriveResumeStep ──────────────────────────────────────────────

describe("deriveResumeStep", () => {
  it("returns 0 for a brand-new DRAFT", () => {
    expect(deriveResumeStep(base)).toBe(0);
  });

  it("returns 0 for non-DRAFT status (should never advance wizard)", () => {
    expect(deriveResumeStep({ ...base, status: "PENDING" })).toBe(0);
    expect(deriveResumeStep({ ...base, status: "APPROVED" })).toBe(0);
    expect(deriveResumeStep({ ...base, status: "REJECTED" })).toBe(0);
  });

  it("returns 1 when types are set but KYC is not done", () => {
    expect(deriveResumeStep({ ...base, types: ["FIELD"] })).toBe(1);
    expect(deriveResumeStep({ ...base, types: ["SURVEYOR", "LAWYER"] })).toBe(1);
  });

  it("returns 2 when BVN is verified", () => {
    expect(
      deriveResumeStep({
        ...base,
        types: ["FIELD"],
        kycMethod: "BVN",
        bvnVerifiedAt: "2026-05-07T10:00:00Z",
        bvnLast4: "1234",
      }),
    ).toBe(2);
  });

  it("returns 2 when ID + selfie are both uploaded", () => {
    expect(
      deriveResumeStep({
        ...base,
        types: ["FIELD"],
        kycMethod: "ID_DOC",
        idDocType: "PASSPORT",
        idDocUploaded: true,
        selfieUploaded: true,
      }),
    ).toBe(2);
  });

  it("returns 1 when BVN method set but not yet verified", () => {
    expect(
      deriveResumeStep({ ...base, types: ["FIELD"], kycMethod: "BVN", bvnVerifiedAt: null }),
    ).toBe(1);
  });

  it("returns 1 when ID_DOC method set but only one file uploaded", () => {
    expect(
      deriveResumeStep({
        ...base,
        types: ["FIELD"],
        kycMethod: "ID_DOC",
        idDocUploaded: true,
        selfieUploaded: false,
      }),
    ).toBe(1);
  });

  it("returns 3 when credentials (coverage states) are saved", () => {
    expect(
      deriveResumeStep({
        ...base,
        types: ["FIELD"],
        kycMethod: "BVN",
        bvnVerifiedAt: "2026-05-07T10:00:00Z",
        coverageStates: ["LAGOS"],
      }),
    ).toBe(3);
  });
});

// ─── validateCredentialsStep ──────────────────────────────────────

const okFields = {
  surveyorLicenceNo: "",
  surveyorLicenceUrl: "",
  nbaLicenceNo: "",
  nbaLicenceUrl: "",
  coverageStates: ["LAGOS"],
  bio: "",
};

describe("validateCredentialsStep", () => {
  it("passes for a FIELD agent with no licence requirements", () => {
    const result = validateCredentialsStep(["FIELD"], okFields);
    expect(result.valid).toBe(true);
    expect(result.error).toBeNull();
  });

  it("fails when SURVEYOR type is selected but licence number is missing", () => {
    const result = validateCredentialsStep(["SURVEYOR"], {
      ...okFields,
      surveyorLicenceNo: "",
      surveyorLicenceUrl: "https://example.com/lic.pdf",
    });
    expect(result.valid).toBe(false);
    expect(result.error).toMatch(/Surveyor licence/);
  });

  it("fails when SURVEYOR type is selected but licence URL is missing", () => {
    const result = validateCredentialsStep(["SURVEYOR"], {
      ...okFields,
      surveyorLicenceNo: "SRV-12345",
      surveyorLicenceUrl: "",
    });
    expect(result.valid).toBe(false);
    expect(result.error).toMatch(/Surveyor licence/);
  });

  it("passes when SURVEYOR type has both licence fields", () => {
    const result = validateCredentialsStep(["SURVEYOR"], {
      ...okFields,
      surveyorLicenceNo: "SRV-12345",
      surveyorLicenceUrl: "https://example.com/lic.pdf",
    });
    expect(result.valid).toBe(true);
  });

  it("fails when LAWYER type is selected but NBA number is missing", () => {
    const result = validateCredentialsStep(["LAWYER"], {
      ...okFields,
      nbaLicenceNo: "",
      nbaLicenceUrl: "https://example.com/nba.pdf",
    });
    expect(result.valid).toBe(false);
    expect(result.error).toMatch(/NBA licence/);
  });

  it("passes when LAWYER type has both NBA fields", () => {
    const result = validateCredentialsStep(["LAWYER"], {
      ...okFields,
      nbaLicenceNo: "NBA-9876",
      nbaLicenceUrl: "https://example.com/nba.pdf",
    });
    expect(result.valid).toBe(true);
  });

  it("fails when no coverage states are selected", () => {
    const result = validateCredentialsStep(["FIELD"], { ...okFields, coverageStates: [] });
    expect(result.valid).toBe(false);
    expect(result.error).toMatch(/coverage state/i);
  });

  it("fails when bio exceeds 300 characters", () => {
    const result = validateCredentialsStep(["FIELD"], {
      ...okFields,
      bio: "x".repeat(301),
    });
    expect(result.valid).toBe(false);
    expect(result.error).toMatch(/300 characters/);
  });

  it("passes when bio is exactly 300 characters", () => {
    const result = validateCredentialsStep(["FIELD"], {
      ...okFields,
      bio: "x".repeat(300),
    });
    expect(result.valid).toBe(true);
  });

  it("fails at first matching rule when multiple types have missing fields", () => {
    const result = validateCredentialsStep(["SURVEYOR", "LAWYER"], {
      ...okFields,
      surveyorLicenceNo: "",
      surveyorLicenceUrl: "",
      nbaLicenceNo: "",
      nbaLicenceUrl: "",
    });
    expect(result.valid).toBe(false);
    expect(result.error).toMatch(/Surveyor licence/);
  });
});
