import { SSE_BASE_BACKOFF_MS, SSE_MAX_RETRIES } from "@lib/config/app";

/**
 * The per-user SSE subscription (PRD §4.9, §N), shared by every consumer in the tab.
 *
 * The chat, notification and earnings counters all listen to the same user-scoped
 * `/api/chat/stream`. One connection serves them all: listeners join and leave, the connection
 * opens with the first and closes with the last. Best-effort — on repeated failure it stops
 * retrying and the counters fall back to their queries' polling, so a dropped push never leaves a
 * counter stale.
 */
export interface UserStreamEvent {
  event: string;
  data: Record<string, unknown>;
}

export type UserStreamListener = (event: UserStreamEvent) => void;

const STREAM_URL = "/api/chat/stream";
const EVENTS = ["chat_message", "chat_unread", "notification", "notification_unread"];

const listeners = new Set<UserStreamListener>();
let source: EventSource | null = null;
let retries = 0;
let retryTimer: ReturnType<typeof setTimeout> | null = null;

function dispatch(message: MessageEvent) {
  let data: Record<string, unknown>;
  try {
    data = JSON.parse(message.data);
  } catch {
    return; // ignore malformed events
  }
  const event: UserStreamEvent = { event: message.type || "message", data };
  listeners.forEach((listener) => listener(event));
}

function connect() {
  const es = new EventSource(STREAM_URL, { withCredentials: true });
  source = es;
  EVENTS.forEach((name) => es.addEventListener(name, dispatch));
  es.addEventListener("heartbeat", () => {
    /* keepalive */
  });
  es.onopen = () => {
    retries = 0;
  };
  es.onerror = () => {
    es.close();
    if (source === es) source = null;
    if (listeners.size === 0 || retries >= SSE_MAX_RETRIES) return;
    const delay = SSE_BASE_BACKOFF_MS * 2 ** retries;
    retries += 1;
    retryTimer = setTimeout(() => {
      retryTimer = null;
      if (listeners.size > 0 && !source) connect();
    }, delay);
  };
}

function disconnect() {
  if (retryTimer) clearTimeout(retryTimer);
  retryTimer = null;
  source?.close();
  source = null;
  retries = 0;
}

/** Listen to the user stream; returns the unsubscribe. The connection is shared across callers. */
export function subscribeUserStream(listener: UserStreamListener): () => void {
  if (typeof EventSource === "undefined") return () => {};

  listeners.add(listener);
  if (!source && !retryTimer) connect();

  return () => {
    listeners.delete(listener);
    if (listeners.size === 0) disconnect();
  };
}
