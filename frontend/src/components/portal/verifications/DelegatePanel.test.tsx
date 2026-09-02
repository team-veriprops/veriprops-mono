import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { CaseDelegate } from "@/types/delegate";

const { delegatesQuery } = vi.hoisted(() => ({
  delegatesQuery: { current: { data: [] as CaseDelegate[], isLoading: false } },
}));

vi.mock("@components/portal/libs/useDelegateQueries", () => ({
  useDelegatesQuery: () => delegatesQuery.current,
  useAuthorizeDelegateMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useConfirmDelegateMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useRevokeDelegateMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

import DelegatePanel from "./DelegatePanel";

function render(data: CaseDelegate[] = [], isLoading = false) {
  delegatesQuery.current = { data, isLoading };
  return renderToStaticMarkup(<DelegatePanel verificationId="v-1" />);
}

const VERIFIED: CaseDelegate = {
  id: "d-1",
  name: "Tunde Adeyemi",
  phoneE164: "+2348012345678",
  verified: true,
};

const AWAITING: CaseDelegate = { ...VERIFIED, verified: false };

describe("DelegatePanel (§7.4.5)", () => {
  it("offers the nomination form when no one is authorized", () => {
    const html = render();
    expect(html).toContain("delegate-name");
    expect(html).toContain("delegate-phone");
    expect(html).toContain("delegate-send");
  });

  it("states the grant's limits before the buyer uses it", () => {
    // A buyer who believes they are sharing the report is surprised twice — here, and
    // when their delegate asks why they cannot open it.
    const html = render();
    expect(html).toContain("status updates only");
    expect(html).toMatch(/never your documents/i);
  });

  it("says only one person can be authorized", () => {
    expect(render()).toMatch(/one person/i);
  });

  it("shows an authorized delegate and the route to remove them", () => {
    const html = render([VERIFIED]);
    expect(html).toContain("Tunde Adeyemi");
    expect(html).toContain("delegate-revoke");
  });

  it("shows the awaiting-code state plainly rather than as a spinner", () => {
    // It can last as long as it takes the buyer to reach the person. Hiding it makes a
    // buyer nominate again because nothing appeared to happen.
    const html = render([AWAITING]);
    expect(html).toContain("waiting for their code");
    expect(html).toContain("delegate-code");
    expect(html).toContain("delegate-confirm");
  });

  it("says an unverified delegate receives nothing yet", () => {
    expect(render([AWAITING])).toMatch(/won&#x27;t receive anything until you do/i);
  });

  it("does not offer the confirm step once verified", () => {
    const html = render([VERIFIED]);
    expect(html).not.toContain("delegate-confirm");
    expect(html).toContain("receiving status updates");
  });

  it("hides the removal warning behind a confirm step", () => {
    const html = render([VERIFIED]);
    expect(html).not.toContain("delegate-revoke-confirm");
  });

  it("never renders a report or document link for the delegate", () => {
    const html = render([VERIFIED]);
    expect(html).not.toContain("/report");
    expect(html).not.toContain("/evidence");
  });
});
