"use client";

import { Toaster } from "@components/3rdparty/ui/toaster";
import { isAutomationEnvironment } from "@lib/automation";
import { publicConfig } from "@lib/config/public";
import { LoadScript } from "@react-google-maps/api";
import { QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "next-themes";
import { useEffect, useState } from "react";
import ConsentReacceptanceModal from "@components/website/auth/ConsentReacceptanceModal";

export function ClientWrapperProvider({ children }: { children: React.ReactNode }) {
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
      (window as any).__app_ready__ = true;
      (window as any).__TEST_MODE__ = true;
    }
  }, []);

  const googleLibraries: ("places")[] = ["places"];

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
        {/* </LoadScript> */}
      </QueryClientProvider>
      <Toaster />
    </ThemeProvider>
  );
}
