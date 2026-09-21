"use client";

import { useEffect, useRef } from "react";

import { subscribeUserStream, type UserStreamEvent } from "@lib/userStream";

export type { UserStreamEvent } from "@lib/userStream";

interface Options {
  onEvent: (event: UserStreamEvent) => void;
  enabled?: boolean;
}

/**
 * Subscribe a component to the per-user SSE stream (PRD §4.9, §N) — the transport behind the Chat,
 * Notifications and earnings counters. Every caller shares one connection (`@lib/userStream`), so
 * mounting several counters never opens several streams.
 */
export function useUserStream({ onEvent, enabled = true }: Options) {
  const onEventRef = useRef(onEvent);
  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);

  useEffect(() => {
    if (!enabled) return;
    return subscribeUserStream((event) => onEventRef.current(event));
  }, [enabled]);
}
