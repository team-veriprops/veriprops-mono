"use client";

import { useEffect } from "react";

export default function SwRegistrar() {
  useEffect(() => {
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js").catch(() => {
        // SW registration failure is non-fatal — app works online without it
      });
    }
  }, []);

  return null;
}
