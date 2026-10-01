import { describe, it, expect, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import { AgentRole } from "@/types/agent";
import { CustomerReportActions } from "@/types/report";
import { VerificationTier } from "@/types/verification";

vi.mock("@components/portal/libs/useRevisionQueries", () => ({
  useOpenDisputeMutation: () => ({ mutate: vi.fn(), isPending: false }),
  useRequestRecheckMutation: () => ({ mutate: vi.fn(), isPending: false }),
  useRequestUpgradeMutation: () => ({ mutate: vi.fn(), isPending: false }),
}));
// Render dialog bodies inline: Radix portals them out of reach of static markup.
vi.mock("@3rdparty/ui/dialog", () => {
  const Pass = ({ children }: { children?: React.ReactNode }) => <div>{children}</div>;
  return { Dialog: Pass, DialogContent: Pass, DialogDescription: Pass, DialogFooter: Pass, DialogHeader: Pass, DialogTitle: Pass };
});

import { ReportActions } from "./ReportActions";

const actions = (over: Partial<CustomerReportActions> = {}): CustomerReportActions => ({
  upgradeTiers: [VerificationTier.PREMIUM],
  disputeRoles: [AgentRole.REGISTRY, AgentRole.FIELD, AgentRole.SURVEYOR],
  disputeMinDescriptionChars: 120,
  ...over,
});

const render = (a: CustomerReportActions) => renderToStaticMarkup(<ReportActions verificationId="v1" actions={a} />);

describe("ReportActions", () => {
  it("lets a dispute name a part of the work the backend lists, or none", () => {
    const html = render(actions());
    expect(html).toContain("Not sure / the whole report");
    expect(html).toContain('value="REGISTRY"');
    expect(html).toContain('value="SURVEYOR"');
    expect(html).not.toContain('value="LAWYER"');
  });

  it("states the backend's minimum description length", () => {
    expect(render(actions())).toContain("0/120 characters minimum");
  });

  it("offers only the upgrade tiers the backend allows, and hides the action when there are none", () => {
    expect(render(actions())).toContain('data-testid="action-upgrade"');
    expect(render(actions({ upgradeTiers: [] }))).not.toContain('data-testid="action-upgrade"');
  });
});
