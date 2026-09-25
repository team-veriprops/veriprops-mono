import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import SignOutOverlay from "./SignOutOverlay";
import { useAuthStore } from "./libs/useAuthStore";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let root: Root | null = null;
let host: HTMLElement | null = null;

function render() {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  act(() => root!.render(<SignOutOverlay />));
}

/** The dialog portals to `<body>`, so assert against the document, not the host node. */
const overlay = () => document.querySelector('[data-testid="signout-overlay"]');

beforeEach(() => useAuthStore.setState({ signingOut: false }));

afterEach(() => {
  act(() => root?.unmount());
  host?.remove();
  root = null;
  host = null;
});

describe("SignOutOverlay", () => {
  it("stays out of the way until a sign-out is actually asked for", () => {
    render();

    expect(overlay()).toBeNull();
  });

  it("appears as soon as the sign-out flag is raised, whichever control raised it", () => {
    render();

    act(() => useAuthStore.getState().setSigningOut(true));

    expect(overlay()).not.toBeNull();
  });

  it("says what is happening rather than showing a bare spinner", () => {
    render();
    act(() => useAuthStore.getState().setSigningOut(true));

    expect(overlay()?.textContent).toContain("Signing you out");
  });

  it("announces itself to assistive technology while the request is in flight", () => {
    render();
    act(() => useAuthStore.getState().setSigningOut(true));

    const status = overlay()?.querySelector('[role="status"]');
    expect(status).not.toBeNull();
    expect(status?.getAttribute("aria-live")).toBe("polite");
  });

  it("offers no way out — the session is already going, and there is nothing to go back to", () => {
    render();
    act(() => useAuthStore.getState().setSigningOut(true));

    // No close button, and Escape must not dismiss it.
    expect(overlay()?.querySelector("button")).toBeNull();
    act(() => {
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    });
    expect(overlay()).not.toBeNull();
  });
});
