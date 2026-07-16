/**
 * Trusted-edge (Cloudflare) request check.
 *
 * The Cloudflare Transform Rule injects `x-edge-auth: <EDGE_AUTH_SECRET>` on every
 * request that traverses the proxy. Traffic that reaches the deployment directly
 * (e.g. a *.vercel.app URL) lacks the header, so rejecting it makes the Cloudflare
 * WAF an enforced boundary instead of an optional route. The backend applies the
 * same check in its EdgeAuthMiddleware — keep header name and semantics in sync.
 *
 * EDGE_AUTH_SECRET is a server-only env var (Doppler-injected; never NEXT_PUBLIC_*).
 * Unset/blank/placeholder disables the check, so local, test, and e2e environments
 * run open without extra configuration.
 */

export const EDGE_AUTH_HEADER = "x-edge-auth";

/** Placeholder sentinel shared with the backend's committed env-file convention. */
const SECRET_PLACEHOLDER = "CHANGE_ME";

export function isEdgeAuthorized(
  headerValue: string | null,
  secret: string | undefined,
): boolean {
  const expected = (secret ?? "").trim();
  if (!expected || expected === SECRET_PLACEHOLDER) return true;

  const supplied = headerValue ?? "";
  // Constant-time comparison (edge runtime has no timingSafeEqual). Comparing
  // lengths first only leaks length, not content.
  if (supplied.length !== expected.length) return false;
  let diff = 0;
  for (let i = 0; i < expected.length; i += 1) {
    diff |= supplied.charCodeAt(i) ^ expected.charCodeAt(i);
  }
  return diff === 0;
}
