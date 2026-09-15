import { describe, it, expect, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

vi.mock("@components/website/auth/libs/useAuthQueries", () => ({
  useSendPhoneOtpMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useVerifyPhoneMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));
vi.mock("@components/3rdparty/ui/use-toast", () => ({ toast: vi.fn() }));

import PayPhoneGate, { phoneGateDefaults } from "./PayPhoneGate";

// The button's utility classes contain "disabled:…", so look for the attribute itself.
const sendButtonDisabled = (html: string) =>
  /\sdisabled=""/.test(html.match(/<button[^>]*data-testid="verify-pay-send-otp"[^>]*>/)?.[0] ?? "");

describe("phoneGateDefaults", () => {
  it("starts from the number on the customer's profile", () => {
    expect(
      phoneGateDefaults({ phone: "8030000001", phoneCountryCode: "GH", phoneDialCode: "+233" }),
    ).toEqual({ countryCode: "GH", dialCode: "+233", phone: "8030000001" });
  });

  it("starts empty when the customer has no number yet", () => {
    expect(phoneGateDefaults(undefined).phone).toBe("");
  });
});

describe("PayPhoneGate", () => {
  it("shows the number on file so the customer can confirm or correct it", () => {
    const html = renderToStaticMarkup(
      <PayPhoneGate
        user={{ phone: "8030000001", phoneCountryCode: "NG", phoneDialCode: "+234" }}
        onVerified={() => {}}
      />,
    );
    expect(html).toContain('data-testid="verify-pay-phone-gate"');
    expect(html).toMatch(/data-testid="verify-pay-phone-input"/);
    expect(html).toContain('value="8030000001"');
    expect(sendButtonDisabled(html)).toBe(false);
  });

  it("cannot send a code until a valid number is entered", () => {
    const html = renderToStaticMarkup(
      <PayPhoneGate
        user={{ phone: "", phoneCountryCode: "NG", phoneDialCode: "+234" }}
        onVerified={() => {}}
      />,
    );
    expect(sendButtonDisabled(html)).toBe(true);
  });
});
