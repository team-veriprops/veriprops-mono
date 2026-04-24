"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

export function useSyncedQueryState<T extends Record<string, any>>(
  initialState: T,
  storageKey?: string
) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  // const [state, setState] = useState<T>(initialState);
  
  // Stabilize the initial state reference
  const initialRef = useRef(initialState);
  const [state, setState] = useState<T>(initialRef.current);

  // Parse query params on mount and whenever searchParams changes
  useEffect(() => {
    const queryState: Partial<T> = {};

    for (const [key, value] of searchParams.entries()) {
      try {
        if (value.includes(",")) {
          (queryState as any)[key] = value.split(",");
        } else if (value === "true" || value === "false") {
          (queryState as any)[key] = value === "true";
        } else if (!isNaN(Number(value)) && value !== "") {
          (queryState as any)[key] = Number(value);
        } else if (value.startsWith("{") || value.startsWith("[")) {
          (queryState as any)[key] = JSON.parse(decodeURIComponent(value));
        } else {
          (queryState as any)[key] = decodeURIComponent(value);
        }
      } catch (e) {
        (queryState as any)[key] = value;
      }
    }

    let next = { ...initialRef.current, ...queryState };

    // Load from localStorage if no query params
    if (storageKey && Object.keys(queryState).length === 0) {
      try {
        const saved = localStorage.getItem(storageKey);
        if (saved) {
          const parsedSaved = JSON.parse(saved);
          setState({ ...initialState, ...parsedSaved });
          return;
        }
      } catch {
        console.warn("Failed to parse localStorage data");
      }
    }

    // Avoid unnecessary re-renders
    setState((prev) =>
      JSON.stringify(prev) === JSON.stringify(next) ? prev : next
    );
  }, [JSON.stringify(searchParams.entries), initialRef.current, storageKey]);

  // Update URL and localStorage
  const updateState = useCallback(
    (
      updates: Partial<T> | ((prev: T) => Partial<T>)
    ) => {
      setState((prev) => {
        const newState =
          typeof updates === "function"
            ? { ...prev, ...updates(prev) }
            : { ...prev, ...updates };

        const params = new URLSearchParams();

        Object.entries(newState).forEach(([key, value]) => {
          if (
            value !== undefined &&
            value !== null &&
            value !== "" &&
            !(Array.isArray(value) && value.length === 0)
          ) {
            if (Array.isArray(value)) {
              params.set(key, value.join(","));
            } else if (typeof value === "object") {
              params.set(key, encodeURIComponent(JSON.stringify(value)));
            } else {
              params.set(key, String(value));
            }
          }
        });

        const newSearch = params.toString();
        const newUrl = `${pathname}${newSearch ? `?${newSearch}` : ""}`;

        // Only navigate if URL actually changed
        if (newUrl !== `${pathname}?${searchParams.toString()}`) {
          router.replace(newUrl);
        }

        if (storageKey) {
          try {
            localStorage.setItem(storageKey, JSON.stringify(newState));
          } catch {
            console.warn("Failed to save to localStorage");
          }
        }

        return newState;
      });
    },
    [pathname, JSON.stringify(searchParams.entries), router, storageKey]
  );

  // Reset to initial state
  const resetState = useCallback(() => {
    setState(initialState);
    router.replace(pathname);
    if (storageKey) {
      localStorage.removeItem(storageKey);
    }
  }, [initialState, pathname, router, storageKey]);

  return [state, updateState, resetState] as const;
}
