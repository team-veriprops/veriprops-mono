import { describe, it, expect } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { AgentRole, CredentialType, GovIdType, KycMethod } from "@/types/agent";
import { AgentWizardState, EMPTY_WIZARD_STATE, KycPhotos } from "./types";
import RolesStep from "./RolesStep";
import KycStep from "./KycStep";
import ReviewStep from "./ReviewStep";

describe("RolesStep", () => {
  it("offers every role as a selectable card", () => {
    const html = renderToStaticMarkup(<RolesStep value={[]} onChange={() => {}} />);
    for (const role of Object.values(AgentRole)) {
      expect(html).toContain(`agent-apply-role-${role.toLowerCase()}`);
    }
  });

  it("marks a chosen role as checked and surfaces the licence gate", () => {
    const html = renderToStaticMarkup(<RolesStep value={[AgentRole.LAWYER]} onChange={() => {}} />);
    // Selected role advertises checked state; regulated roles show their licence requirement.
    expect(html).toContain('aria-checked="true"');
    expect(html).toContain("NBA licence required");
  });
});

const DOCUMENT_TYPES = [GovIdType.PASSPORT, GovIdType.DRIVERS_LICENCE, GovIdType.VOTERS_CARD];
const kycStep = (value: AgentWizardState["kyc"], photos: KycPhotos = {}) => renderToStaticMarkup(
  <KycStep value={value} onChange={() => {}} photos={photos} onPhotosChange={() => {}} documentIdTypes={DOCUMENT_TYPES} />,
);

describe("KycStep", () => {
  it("shows the BVN field on the BVN method", () => {
    const html = kycStep({ method: KycMethod.BVN });
    expect(html).toContain("agent-apply-bvn");
    expect(html).toContain("Recommended");
  });

  it("shows government-ID fields on the gov-ID method", () => {
    const html = kycStep({ method: KycMethod.GOV_ID });
    expect(html).toContain("agent-apply-idtype");
    expect(html).toContain("agent-apply-idnumber");
  });

  it("asks for a selfie on every method", () => {
    expect(kycStep({ method: KycMethod.BVN })).toContain('data-testid="agent-apply-selfie-file"');
    expect(kycStep({ method: KycMethod.GOV_ID, idType: GovIdType.NIN })).toContain('data-testid="agent-apply-selfie"');
  });

  it("asks for a photo of the document only for the IDs a reviewer checks", () => {
    expect(kycStep({ method: KycMethod.GOV_ID, idType: GovIdType.PASSPORT })).toContain('data-testid="agent-apply-id-document"');
    expect(kycStep({ method: KycMethod.GOV_ID, idType: GovIdType.NIN })).not.toContain("agent-apply-id-document");
  });

  it("shows a taken selfie with a way to retake it", () => {
    const html = kycStep({ method: KycMethod.BVN }, { selfie: "/9j/abc" });
    expect(html).toContain('data-testid="agent-apply-selfie-preview"');
    expect(html).toContain("data:image/jpeg;base64,/9j/abc");
    expect(html).toContain('data-testid="agent-apply-selfie-retake"');
  });
});

describe("ReviewStep", () => {
  it("renders humanized role, identity, and credential summaries", () => {
    const html = renderToStaticMarkup(
      <ReviewStep
        state={{
          ...EMPTY_WIZARD_STATE,
          roles: [AgentRole.FIELD, AgentRole.LAWYER],
          kyc: { method: KycMethod.GOV_ID },
          credentials: [{ role: AgentRole.LAWYER, credentialType: CredentialType.NBA_LICENCE }],
        }}
        update={() => {}}
        termsAccepted={false}
        onTermsAcceptedChange={() => {}}
      />,
    );
    // Enums are humanized, never rendered raw.
    expect(html).toContain("Field, Lawyer");
    expect(html).toContain("Government ID");
    expect(html).not.toContain("GOV_ID");
    expect(html).not.toContain(">FIELD<");
  });
});
