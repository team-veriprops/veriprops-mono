import { describe, it, expect, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

const verification: { data: { publicLookupEnabled?: boolean | null } | null } = { data: null };
vi.mock("@components/portal/libs/useVerificationQueries", () => ({
  useVerificationQuery: () => verification,
}));
vi.mock("@components/portal/libs/useShareQueries", () => ({
  useSharesQuery: () => ({ data: [] }),
  useCreateShareMutation: () => ({ mutate: vi.fn(), isPending: false }),
  useRevokeShareMutation: () => ({ mutate: vi.fn(), isPending: false }),
  useSetPublicVisibilityMutation: () => ({ mutate: vi.fn(), isPending: false }),
}));
// Radix renders a dialog's content through a portal, which static markup cannot follow.
vi.mock("@3rdparty/ui/dialog", () => ({
  Dialog: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  DialogContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  DialogHeader: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  DialogTitle: ({ children }: { children: React.ReactNode }) => <h2>{children}</h2>,
  DialogDescription: ({ children }: { children: React.ReactNode }) => <p>{children}</p>,
}));

import { ReportShareModal } from "./ReportShareModal";

const render = () =>
  renderToStaticMarkup(<ReportShareModal verificationId="v1" vid="VP-2026-ABC" open onOpenChange={() => {}} />);

describe("ReportShareModal — public lookup", () => {
  it("says the lookup is off and offers to turn it on", () => {
    verification.data = { publicLookupEnabled: false };
    const html = render();
    expect(html).toContain("Public lookup is off");
    expect(html).toMatch(/data-testid="share-public-toggle"[^>]*>Turn on/);
  });

  it("says the lookup is on and lets the customer turn it off again", () => {
    verification.data = { publicLookupEnabled: true };
    const html = render();
    expect(html).toContain("Public lookup is on");
    expect(html).toMatch(/data-testid="share-public-toggle"[^>]*>Turn off/);
  });
});
