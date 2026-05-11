"use client";

import { useEffect, useRef } from "react";

export interface VerificationStreamEvent {
  event: string;
  data: Record<string, unknown>;
}

interface Options {
  vid: string;
  onEvent: (event: VerificationStreamEvent) => void;
  enabled?: boolean;
}

const MAX_RETRIES = 3;
const BASE_BACKOFF_MS = 1000;

export function useVerificationStream({ vid, onEvent, enabled = true }: Options) {
  const esRef = useRef<EventSource | null>(null);
  const retriesRef = useRef(0);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  useEffect(() => {
    if (!enabled) return;

    // SSE not supported — rely on polling in useVerificationTracking (60s interval)
    if (typeof EventSource === "undefined") return;

    function connect() {
      if (esRef.current) {
        esRef.current.close();
      }
      const es = new EventSource(`/api/portal/verifications/${vid}/stream`, { withCredentials: true });
      esRef.current = es;

      es.addEventListener("message", handleMsg);
      es.addEventListener("status_changed", handleMsg);
      es.addEventListener("task_updated", handleMsg);
      es.addEventListener("conflict_detected", handleMsg);
      es.addEventListener("report_released", handleMsg);
      es.addEventListener("heartbeat", () => { /* keepalive */ });

      es.onerror = () => {
        es.close();
        esRef.current = null;
        if (retriesRef.current < MAX_RETRIES) {
          const delay = BASE_BACKOFF_MS * Math.pow(2, retriesRef.current);
          retriesRef.current += 1;
          timeoutRef.current = setTimeout(connect, delay);
        }
        // After MAX_RETRIES, silently fall back to polling
      };

      es.onopen = () => {
        retriesRef.current = 0;
      };
    }

    function handleMsg(e: MessageEvent) {
      try {
        const data = JSON.parse(e.data);
        onEventRef.current({ event: e.type || "message", data });
      } catch {
        // ignore malformed events
      }
    }

    connect();

    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }
    };
  }, [vid, enabled]);
}
