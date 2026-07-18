"use client";

import { Toaster } from "@components/3rdparty/ui/toaster";
import { isAutomationEnvironment } from "@lib/automation";
import { QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "next-themes";
import { useEffect, useState } from "react";
import ConsentReacceptanceModal from "@components/website/auth/ConsentReacceptanceModal";
import SessionRecoveryOverlay from "@components/website/auth/SessionRecoveryOverlay";
import { useProactiveSessionRefresh } from "@components/website/auth/libs/useProactiveSessionRefresh";
import { usePendingLogoutRetry } from "@components/website/auth/libs/usePendingLogoutRetry";

/** Rendered under `QueryClientProvider` — `usePendingLogoutRetry` needs a QueryClient
 * in context (it drives `useLogoutMutation`), which isn't available in the parent's
 * own render (a component can't consume a context it's about to create). */
function PendingLogoutRetry() {
  usePendingLogoutRetry();
  return null;
}

export function ClientWrapperProvider({ children }: { children: React.ReactNode }) {
  // Keep-alive: silently refresh ahead of access-token expiry (no-op signed out).
  useProactiveSessionRefresh();

  // Use useState to ensure the client is stable across renders
  const [queryClient] = useState(
    () =>
      new QueryClient({
        queryCache: new QueryCache({
        //   onError: (error) =>
        //     toast.error(`Something went wrong: ${error.message}`),
        }),
      })
  );

  useEffect(() => {
    if (isAutomationEnvironment()) {
      window.__app_ready__ = true;
      window.__TEST_MODE__ = true;
    }
  }, []);

  return (
    <ThemeProvider
      attribute="class"
      defaultTheme="light"
      enableSystem
      disableTransitionOnChange
    >
      <QueryClientProvider client={queryClient}>
        {/* <LoadScript
          googleMapsApiKey={publicConfig.googleMapsApiKey!}
          libraries={googleLibraries}
        > */}
        {children}
        {/* The modal is auto-suppressed when there's no session, so it costs
            nothing on public pages. PRD §3.2: re-acceptance after a version bump. */}
        <ConsentReacceptanceModal />
        {/* Session-recovery UX: reconnect attempts + expired-session handoff,
            driven by FetchHttpClient via sessionRecoveryStore. */}
        <SessionRecoveryOverlay />
        {/* Flush a logout that couldn't reach the backend once connectivity returns. */}
        <PendingLogoutRetry />
        {/* </LoadScript> */}
      </QueryClientProvider>
      <Toaster />
    </ThemeProvider>
  );
}
