import { describe, it, expect } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { AgentRole, CredentialType, KycMethod } from "@/types/agent";
import { EMPTY_WIZARD_STATE } from "./types";
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

describe("KycStep", () => {
  it("shows the BVN field on the BVN method", () => {
    const html = renderToStaticMarkup(
      <KycStep value={{ method: KycMethod.BVN }} onChange={() => {}} />,
    );
    expect(html).toContain("agent-apply-bvn");
    expect(html).toContain("Recommended");
  });

  it("shows government-ID fields on the gov-ID method", () => {
    const html = renderToStaticMarkup(
      <KycStep value={{ method: KycMethod.GOV_ID }} onChange={() => {}} />,
    );
    expect(html).toContain("agent-apply-idtype");
    expect(html).toContain("agent-apply-idnumber");
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
