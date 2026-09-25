import { beforeEach, describe, expect, it } from "vitest";
import { useAuthStore } from "./useAuthStore";
import type { AuthSession } from "@components/website/auth/models";

const FAKE_SESSION = {
  accessTokenExpiresAt: "2026-07-17T13:00:00Z",
  refreshTokenExpiresAt: "2026-08-16T12:00:00Z",
  user: { id: "u1" },
} as unknown as AuthSession;

beforeEach(() => {
  useAuthStore.setState({ session: null, pendingLogout: false, signingOut: false, hydrated: false });
});

describe("useAuthStore pendingLogout", () => {
  it("defaults to false", () => {
    expect(useAuthStore.getState().pendingLogout).toBe(false);
  });

  it("setPendingLogout sets the flag", () => {
    useAuthStore.getState().setPendingLogout(true);
    expect(useAuthStore.getState().pendingLogout).toBe(true);
  });

  it("setSession clears a queued pendingLogout — a re-confirmed session always wins over a stale intent", () => {
    useAuthStore.getState().setPendingLogout(true);

    useAuthStore.getState().setSession(FAKE_SESSION);

    expect(useAuthStore.getState().pendingLogout).toBe(false);
    expect(useAuthStore.getState().session).toBe(FAKE_SESSION);
  });

  it("clear() leaves pendingLogout untouched — the offline-logout retry must survive local cleanup", () => {
    useAuthStore.getState().setSession(FAKE_SESSION);
    useAuthStore.getState().setPendingLogout(true);

    useAuthStore.getState().clear();

    expect(useAuthStore.getState().session).toBeNull();
    expect(useAuthStore.getState().pendingLogout).toBe(true);
  });
});

describe("useAuthStore signingOut", () => {
  it("defaults to false", () => {
    expect(useAuthStore.getState().signingOut).toBe(false);
  });

  it("setSigningOut raises the flag the sign-out overlay renders from", () => {
    useAuthStore.getState().setSigningOut(true);
    expect(useAuthStore.getState().signingOut).toBe(true);
  });

  it("clear() leaves signingOut raised — it runs before the redirect, and dropping the overlay there would flash the signed-in page", () => {
    useAuthStore.getState().setSession(FAKE_SESSION);
    useAuthStore.getState().setSigningOut(true);

    useAuthStore.getState().clear();

    expect(useAuthStore.getState().session).toBeNull();
    expect(useAuthStore.getState().signingOut).toBe(true);
  });

  it("setSession lowers signingOut — a confirmed session is not a sign-out in progress", () => {
    useAuthStore.getState().setSigningOut(true);

    useAuthStore.getState().setSession(FAKE_SESSION);

    expect(useAuthStore.getState().signingOut).toBe(false);
  });

  it("is not persisted — a tab killed mid-sign-out must not reopen stuck behind the overlay", () => {
    const persisted = useAuthStore.persist.getOptions().partialize!({
      ...useAuthStore.getState(),
      signingOut: true,
    });
    expect(persisted).not.toHaveProperty("signingOut");
  });
});
