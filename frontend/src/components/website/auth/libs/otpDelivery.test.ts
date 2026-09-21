import { describe, expect, it } from "vitest";

import { OTP_NOT_DELIVERED_MESSAGE, otpDeliveryError } from "./otpDelivery";

// A code request returns 2xx even when nothing was delivered: the backend stores the code first
// and keeps delivery best-effort. Treating that as success is what left customers staring at an
// entry box for a code that was never sent.
describe("otpDeliveryError", () => {
  it("is silent when the code was delivered", () => {
    expect(otpDeliveryError({ resendIn: 600, delivered: true })).toBeNull();
  });

  it("explains itself when dispatch did not complete", () => {
    expect(otpDeliveryError({ resendIn: 600, delivered: false })).toBe(OTP_NOT_DELIVERED_MESSAGE);
  });

  it("treats a missing result as undelivered rather than assuming success", () => {
    expect(otpDeliveryError(undefined)).toBe(OTP_NOT_DELIVERED_MESSAGE);
    expect(otpDeliveryError(null)).toBe(OTP_NOT_DELIVERED_MESSAGE);
  });
});
