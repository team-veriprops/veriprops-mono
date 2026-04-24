"use client";

import { useEffect } from "react";

export function useBodyOverflowHidden(active: boolean) {
  useEffect(() => {
    if (active) {
      document.body.classList.add("overflow-hidden");
    } else {
      document.body.classList.remove("overflow-hidden");
    }

    // cleanup in case the component unmounts while active
    return () => {
      document.body.classList.remove("overflow-hidden");
    };
  }, [active]);
}
