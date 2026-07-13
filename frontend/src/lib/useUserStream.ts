"use client";

import { useEffect, useRef } from "react";

import { SSE_BASE_BACKOFF_MS, SSE_MAX_RETRIES } from "@lib/config/app";

/**
 * Per-user SSE subscription (PRD §4.9, §N) — the transport behind the Chat and
 * Notifications top-nav counters. Mirrors `useVerificationStream` but subscribes to the
 * user-scoped `/api/chat/stream`. Best-effort: on repeated failure it silently falls back
 * to the queries' polling, so a dropped push never leaves a counter stale.
 */
export interface UserStreamEvent {
  event: string;
  data: Record<string, unknown>;
}

interface Options {
  onEvent: (event: UserStreamEvent) => void;
  enabled?: boolean;
}

const MAX_RETRIES = SSE_MAX_RETRIES;
const BASE_BACKOFF_MS = SSE_BASE_BACKOFF_MS;
const EVENTS = ["chat_message", "chat_unread", "notification", "notification_unread"];

export function useUserStream({ onEvent, enabled = true }: Options) {
  const esRef = useRef<EventSource | null>(null);
  const retriesRef = useRef(0);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onEventRef = useRef(onEvent);
  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);

  useEffect(() => {
    if (!enabled) return;
    if (typeof EventSource === "undefined") return;

    function handleMsg(e: MessageEvent) {
      try {
        const data = JSON.parse(e.data);
        onEventRef.current({ event: e.type || "message", data });
      } catch {
        // ignore malformed events
      }
    }

    function connect() {
      if (esRef.current) esRef.current.close();
      const es = new EventSource(`/api/chat/stream`, { withCredentials: true });
      esRef.current = es;

      EVENTS.forEach((name) => es.addEventListener(name, handleMsg));
      es.addEventListener("heartbeat", () => { /* keepalive */ });

      es.onerror = () => {
        es.close();
        esRef.current = null;
        if (retriesRef.current < MAX_RETRIES) {
          const delay = BASE_BACKOFF_MS * Math.pow(2, retriesRef.current);
          retriesRef.current += 1;
          timeoutRef.current = setTimeout(connect, delay);
        }
      };
      es.onopen = () => {
        retriesRef.current = 0;
      };
    }

    connect();
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }
    };
  }, [enabled]);
}
