"use client";

import { useSyncExternalStore } from "react";

/** Hydration happens once and never reverts, so the store has nothing to publish. */
const subscribe = () => () => {};
const getSnapshot = () => true;
const getServerSnapshot = () => false;

/**
 * False while rendering on the server and during the hydration render; true once React has
 * hydrated and its event handlers are attached.
 *
 * Forms gate submission on this. Before hydration a form's `onSubmit` does not exist yet, so
 * submitting is handled by the browser instead: it navigates and appends every field to the
 * URL as a query parameter. On a credential form that writes the password into browser
 * history, the `Referer` header, and the reverse proxy's access log.
 *
 * Built on `useSyncExternalStore` rather than a `setState` in an effect: it reads the server
 * snapshot during hydration and the client one immediately after, which is the same signal
 * without the cascading render (and the `react-hooks/set-state-in-effect` breach) an effect
 * would bring.
 */
export function useHydrated(): boolean {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}
