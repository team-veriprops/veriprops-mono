/**
 * Navigation after the session's identity has changed (PRD §3.2 persona grants).
 *
 * Taking up a hat rotates the session cookies, which is what `proxy.ts` decides routing from. But
 * the client router has been prefetching under the *old* personas the whole time the wizard was on
 * screen — and every one of those prefetches was answered by the guard's redirect, then cached. A
 * `router.push` to the newly opened area replays that cached verdict without asking the guard
 * again, so the user is sent back exactly as they were before the grant, with no request made and
 * nothing to show for it.
 *
 * A full document load is the honest response: the cookies, the auth store, the router cache and
 * the nav were all built for a person who no longer exists, and every one of them is rebuilt from
 * the new session. This happens once when someone takes up a hat, so the cost is irrelevant.
 */
export function navigateAfterPersonaChange(href: string): void {
  window.location.assign(href);
}
