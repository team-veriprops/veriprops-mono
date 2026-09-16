/**
 * What a request for a verification code reports back, and what to say when the code is not
 * actually on its way.
 *
 * The backend stores the code before dispatching it and keeps delivery best-effort — a failed
 * send is recorded for retry rather than failing the request — so a 2xx does **not** mean the
 * customer will receive anything. `delivered` is what distinguishes the two, and every surface
 * that asks for a code has to check it: presenting a code-entry box for a code that is never
 * coming leaves the customer waiting on nothing.
 */

/** Mirrors the backend's `OtpSendResultDto`. */
export interface OtpSendResult {
  /** Seconds until another code may be requested. */
  resendIn: number;
  /** False when dispatch did not complete; the code may still arrive via the retry ladder. */
  delivered: boolean;
}

export const OTP_NOT_DELIVERED_MESSAGE =
  "We couldn't send your code just now. Please try again in a moment.";

/** The message to show for *result*, or null when the code is genuinely on its way. */
export function otpDeliveryError(result?: OtpSendResult | null): string | null {
  return result?.delivered ? null : OTP_NOT_DELIVERED_MESSAGE;
}
