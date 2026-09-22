/**
 * Stacking order for the app's fixed layers, lowest first:
 *
 * - `z-40` — persistent chrome that stays on screen (AppShell mobile scrim, WhatsApp widget).
 * - `z-45` — {@link PAGE_OVERLAY_LAYER}: full-screen page layers (wizards, the report access gate).
 * - `z-50` — {@link PORTAL_LAYER_Z}: everything Radix portals to `<body>` (dialogs, selects,
 *   popovers, tooltips, dropdowns) plus `DetailDrawer`.
 * - `z-100` — toasts.
 *
 * Page layers must stay under the portal tier. A global mandatory modal (updated-terms
 * re-acceptance, session recovery) can open over any page, and an open Radix modal disables
 * pointer events everywhere else; a page layer painted above it leaves the user a visible screen
 * they cannot use. A picker opened from inside a page layer would likewise render behind it.
 */
export const PAGE_OVERLAY_LAYER = "z-45";

/** z-index of the vendored Radix portal layers (`3rdparty/ui/*`) — the ceiling for page layers. */
export const PORTAL_LAYER_Z = 50;
