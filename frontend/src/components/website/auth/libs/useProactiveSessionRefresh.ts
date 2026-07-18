"use client";

import { useEffect } from "react";
import { fetchHttpClient } from "@/containers";
import { SESSION_REFRESH_LEAD_MS } from "@lib/config/app";
import { useAuthStore } from "./useAuthStore";

/**
 * Milliseconds until the proactive refresh should fire: `SESSION_REFRESH_LEAD_MS`
 * before the access token expires, clamped to "now" when already inside the lead
 * window (or past expiry). `null` for an unparseable timestamp — don't schedule.
 */
export function computeRefreshDelay(accessTokenExpiresAt: string, nowMs: number): number | null {
  const expiresAtMs = Date.parse(accessTokenExpiresAt);
  if (Number.isNaN(expiresAtMs)) return null;
  return Math.max(0, expiresAtMs - SESSION_REFRESH_LEAD_MS - nowMs);
}

/**
 * Keeps the session alive ahead of access-token expiry so users rarely hit a
 * 401 at all (mounted once in `ClientWrapperProvider`).
 *
 * Refreshes only while the tab is visible; a tab that was hidden across the
 * expiry window refreshes immediately on return. Every successful refresh
 * re-syncs `accessTokenExpiresAt` in `useAuthStore` (via the recovery-store
 * bridge), which re-runs the effect and schedules the next cycle. Failures are
 * surfaced by the shared retry/overlay machinery in `FetchHttpClient` — this
 * hook never handles them itself.
 */
export function useProactiveSessionRefresh(): void {
  const accessTokenExpiresAt = useAuthStore((s) => s.session?.accessTokenExpiresAt ?? null);

  useEffect(() => {
    if (!accessTokenExpiresAt) return;

    const refreshIfVisible = () => {
      if (document.visibilityState === "visible") {
        void fetchHttpClient.refreshSession().catch(() => {
          // Recovery UI + login handoff are owned by sessionRecoveryStore.
        });
      }
    };

    const delay = computeRefreshDelay(accessTokenExpiresAt, Date.now());
    if (delay === null) return;
    const timer = setTimeout(refreshIfVisible, delay);

    const onVisibility = () => {
      if (document.visibilityState !== "visible") return;
      // The scheduled timer skips refreshes while hidden — catch up on return
      // once inside (or past) the lead window.
      if (computeRefreshDelay(accessTokenExpiresAt, Date.now()) === 0) {
        refreshIfVisible();
      }
    };
    document.addEventListener("visibilitychange", onVisibility);

    return () => {
      clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [accessTokenExpiresAt]);
}
