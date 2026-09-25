import { describe, it, expect, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

vi.mock("@components/website/auth/libs/useAuthQueries", () => ({
  useGrantCustomerPersonaMutation: () => ({ mutateAsync: () => new Promise(() => {}), isPending: true }),
}));

import VerifyPropertyContainer from "./VerifyPropertyContainer";

describe("VerifyPropertyContainer", () => {
  /**
   * Taking up the customer hat is a round trip that re-mints the session. A blank screen for its
   * duration reads as the click having done nothing, so the wait is stated in words. The browser
   * suite cannot hold this reliably — on a fast stack the grant lands before a check can see it —
   * so the wording is pinned here.
   */
  it("says what it is doing while the customer account is opened", () => {
    const html = renderToStaticMarkup(<VerifyPropertyContainer />);

    expect(html).toContain('data-testid="agent-verify-property-loading"');
    expect(html).toContain("Opening your customer account");
    expect(html).not.toContain("agent-verify-property-error");
  });
});
