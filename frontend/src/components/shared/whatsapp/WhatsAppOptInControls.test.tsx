import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import WhatsAppOptInControls from "./WhatsAppOptInControls";
import { NO_WHATSAPP_CONSENT, WhatsAppConsent } from "@/types/whatsappConsent";

function render(consent: WhatsAppConsent = NO_WHATSAPP_CONSENT, disabled = false) {
  return renderToStaticMarkup(
    <WhatsAppOptInControls consent={consent} onChange={vi.fn()} disabled={disabled} />,
  );
}

describe("WhatsAppOptInControls (§26.4.6)", () => {
  it("renders two separate controls, not one bundled opt-in", () => {
    const html = render();
    expect(html).toContain("wa-optin-utility");
    expect(html).toContain("wa-optin-marketing");
  });

  it("starts with both unticked — a pre-ticked box is not consent", () => {
    const html = render();
    // Radix renders the checked state onto the trigger; unchecked must be what a
    // customer who has never been asked sees.
    expect(html).not.toContain('data-state="checked"');
  });

  it("reflects a consent the backend already holds", () => {
    const html = render({ utility: true, marketing: false });
    expect(html).toContain('data-state="checked"');
  });

  it("asks the two questions §26.4.6 specifies, separately", () => {
    const html = render();
    expect(html).toContain("progress updates about this verification");
    expect(html).toContain("news and offers");
  });

  it("says email is unaffected — WA-35's promise, where the customer decides", () => {
    expect(render()).toContain("email you everything important");
  });

  it("names STOP as the chat-side revocation route (D64)", () => {
    expect(render()).toContain("STOP");
  });

  it("can be disabled while a save is in flight", () => {
    expect(render(NO_WHATSAPP_CONSENT, true)).toContain("disabled");
  });
});
