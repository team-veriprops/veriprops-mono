"use client";

import { Toaster } from "@components/3rdparty/ui/toaster";
import { publicConfig } from "@lib/config/public";
import { LoadScript } from "@react-google-maps/api";
import { QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "next-themes";
import { useState, useEffect } from "react";

export function ClientWrapperProvider({ children }: { children: React.ReactNode }) {
  const [mounted, setMounted] = useState<boolean>(false);
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
    setTimeout(()=>{
    setMounted(true);
    }, 0)
  }, []);

  if (!mounted) return null;

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
        {/* </LoadScript> */}
      </QueryClientProvider>
      <Toaster />
    </ThemeProvider>
  );
}
