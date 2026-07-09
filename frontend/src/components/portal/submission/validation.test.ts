import { describe, it, expect } from "vitest";
import { PropertyKind } from "@/types/verification";
import { EMPTY_SUBMISSION, SubmissionState } from "./types";
import { canAdvanceSubmissionStep } from "./validation";

const withState = (patch: Partial<SubmissionState>): SubmissionState => ({ ...EMPTY_SUBMISSION, ...patch });
const withProperty = (patch: Partial<SubmissionState["property"]>): SubmissionState =>
  ({ ...EMPTY_SUBMISSION, property: { ...EMPTY_SUBMISSION.property, ...patch } });

describe("canAdvanceSubmissionStep", () => {
  it("blocks property step until an address or landmark is given", () => {
    expect(canAdvanceSubmissionStep(0, EMPTY_SUBMISSION)).toBe(false);
    expect(canAdvanceSubmissionStep(0, withProperty({ address: "12 Lekki Rd" }))).toBe(true);
  });

  it("accepts a landmark alone as the mandatory escape valve", () => {
    expect(canAdvanceSubmissionStep(0, withProperty({ landmark: "near the big church" }))).toBe(true);
  });

  it("requires a tier on the pricing step", () => {
    expect(canAdvanceSubmissionStep(1, EMPTY_SUBMISSION)).toBe(true); // default STANDARD is set
  });

  it("blocks consent step until VERIFICATION_TERMS accepted", () => {
    expect(canAdvanceSubmissionStep(2, withState({ consentAccepted: false }))).toBe(false);
    expect(canAdvanceSubmissionStep(2, withState({ consentAccepted: true }))).toBe(true);
  });

  it("permits the building type", () => {
    expect(canAdvanceSubmissionStep(0, withProperty({ propertyType: PropertyKind.BUILDING, address: "x" }))).toBe(true);
  });
});
