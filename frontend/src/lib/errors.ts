import { HttpError, UNDESCRIBED_ERROR_MESSAGE } from "./FetchHttpClient";

/**
 * The one policy for turning a failed request into words on screen.
 *
 * Only a client error (4xx) carries a message written for the user — "Invalid username or
 * password", "That email is already registered" — so only that is ever shown. A server error is
 * never shown as the server phrased it, even though the backend already answers every 5xx with a
 * safe sentence: this module is the second line, so one handler that forgets can never put SQL,
 * a host error or a provider's reply on a user's screen. Failures with no response at all
 * (offline, timed out) only exist on this side, so their words live here too.
 */

export const SERVER_ERROR_MESSAGE = "Something went wrong on our side. Please try again.";
export const OFFLINE_MESSAGE = "We couldn't reach Veriprops. Check your connection and try again.";
export const TIMEOUT_MESSAGE = "That took too long to respond. Please try again.";
const DEFAULT_FALLBACK = "Something went wrong. Please try again.";

function isServerError(error: HttpError): boolean {
  return error.httpStatus !== undefined && error.httpStatus >= 500;
}

/** The reference the backend logged the failure under, so a user's screenshot finds the log line. */
function withReference(message: string, reference: string | undefined): string {
  return reference ? `${message} Ref: ${reference}` : message;
}

/**
 * Words for *error*, safe to render.
 *
 * `fallback` is for the caller's context ("Could not save that preference.") and is used when there
 * is nothing better to say. It is deliberately *not* used for a server failure: a caller's fallback
 * can blame the user ("Email or password is incorrect.") for an outage that is ours.
 */
export function getErrorMessage(error: unknown, fallback: string = DEFAULT_FALLBACK): string {
  if (!(error instanceof HttpError)) {
    // A runtime error's text ("Cannot read properties of undefined") is for developers.
    return fallback;
  }
  if (error.kind === "network") return OFFLINE_MESSAGE;
  if (error.kind === "timeout") return TIMEOUT_MESSAGE;
  if (isServerError(error)) return withReference(SERVER_ERROR_MESSAGE, error.reference);
  return error.message && error.message !== UNDESCRIBED_ERROR_MESSAGE ? error.message : fallback;
}

/** The backend rejected the credentials themselves — the only failure a sign-in lockout may count. */
export function isCredentialRejection(error: unknown): boolean {
  return error instanceof HttpError && error.httpStatus === 401;
}
