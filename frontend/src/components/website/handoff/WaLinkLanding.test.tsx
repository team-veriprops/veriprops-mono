import { describe, it, expect, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

const { startSpy, confirmSpy } = vi.hoisted(() => ({
  startSpy: vi.fn(),
  confirmSpy: vi.fn(),
}));

vi.mock("@components/account/libs/useWhatsAppLinkQueries", () => ({
  useStartWhatsAppLinkFromTokenMutation: () => ({ mutateAsync: startSpy, isPending: false }),
  useConfirmWhatsAppLinkFromTokenMutation: () => ({ mutateAsync: confirmSpy, isPending: false }),
}));
vi.mock("@components/website/auth/libs/useAuthQueries", () => ({
  usePublicConfigQuery: () => ({ data: { whatsappNumber: "2349167624347" } }),
}));

import WaLinkLanding from "./WaLinkLanding";

describe("WaLinkLanding", () => {
  it("does not reveal a number before the server names one", () => {
    // The number is the token's to supply. Rendering anything from the URL would make
    // the page assert an identity the backend has not confirmed.
    const html = renderToStaticMarkup(<WaLinkLanding token="signed-token" />);
    expect(html).toContain("Sending your code");
    expect(html).not.toContain("+234");
  });

  it("sends the code from an effect, not during render", () => {
    // Starting a link is a rate-limited side effect and the URL is fetched by WhatsApp
    // to build a link preview — a render-time call would burn the customer's allowance
    // before they ever opened the page.
    startSpy.mockReset();
    renderToStaticMarkup(<WaLinkLanding token="signed-token" />);
    expect(startSpy).not.toHaveBeenCalled();
  });

  it("never asks the browser for the number it is claiming", () => {
    const html = renderToStaticMarkup(<WaLinkLanding token="signed-token" />);
    expect(html).not.toContain('data-testid="wa-link-phone"');
  });
});
