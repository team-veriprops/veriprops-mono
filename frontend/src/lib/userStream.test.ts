import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SSE_BASE_BACKOFF_MS, SSE_MAX_RETRIES } from "./config/app";
import { subscribeUserStream, type UserStreamEvent } from "./userStream";

type Listener = (event: MessageEvent) => void;

/** Records every connection the store opens, and lets a test push events or failures into it. */
class FakeEventSource {
  static instances: FakeEventSource[] = [];
  readonly url: string;
  readonly listeners = new Map<string, Listener[]>();
  onerror: (() => void) | null = null;
  onopen: (() => void) | null = null;
  closed = false;

  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
  }

  addEventListener(name: string, listener: Listener) {
    this.listeners.set(name, [...(this.listeners.get(name) ?? []), listener]);
  }

  emit(name: string, data: unknown) {
    for (const listener of this.listeners.get(name) ?? []) {
      listener({ type: name, data: JSON.stringify(data) } as MessageEvent);
    }
  }

  fail() {
    this.onerror?.();
  }

  close() {
    this.closed = true;
  }
}

const open = () => FakeEventSource.instances.filter((es) => !es.closed);

beforeEach(() => {
  FakeEventSource.instances = [];
  vi.stubGlobal("EventSource", FakeEventSource);
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

// The chat, notification and earnings counters all listen to the same per-user stream. Each used
// to open its own connection, so one tab held three and, on a broken session, retried three times
// over; the store shares one connection per tab.
describe("subscribeUserStream", () => {
  it("serves every subscriber from a single connection", () => {
    const chat: UserStreamEvent[] = [];
    const notifications: UserStreamEvent[] = [];
    const unsubscribeChat = subscribeUserStream((event) => chat.push(event));
    const unsubscribeNotifications = subscribeUserStream((event) => notifications.push(event));

    expect(FakeEventSource.instances).toHaveLength(1);
    FakeEventSource.instances[0].emit("chat_unread", { count: 2 });

    expect(chat).toEqual([{ event: "chat_unread", data: { count: 2 } }]);
    expect(notifications).toEqual([{ event: "chat_unread", data: { count: 2 } }]);

    unsubscribeChat();
    unsubscribeNotifications();
  });

  it("closes the connection only when its last subscriber leaves", () => {
    const unsubscribeFirst = subscribeUserStream(vi.fn());
    const unsubscribeSecond = subscribeUserStream(vi.fn());

    unsubscribeFirst();
    expect(open()).toHaveLength(1);

    unsubscribeSecond();
    expect(open()).toHaveLength(0);

    // A later subscriber starts a fresh connection.
    const unsubscribeLater = subscribeUserStream(vi.fn());
    expect(open()).toHaveLength(1);
    unsubscribeLater();
  });

  it("reconnects with backoff up to the retry budget, then gives up", () => {
    const unsubscribe = subscribeUserStream(vi.fn());

    for (let attempt = 0; attempt < SSE_MAX_RETRIES; attempt++) {
      FakeEventSource.instances.at(-1)!.fail();
      expect(open()).toHaveLength(0);
      vi.advanceTimersByTime(SSE_BASE_BACKOFF_MS * 2 ** attempt);
      expect(open()).toHaveLength(1);
    }

    FakeEventSource.instances.at(-1)!.fail();
    vi.advanceTimersByTime(SSE_BASE_BACKOFF_MS * 2 ** SSE_MAX_RETRIES * 4);
    expect(open()).toHaveLength(0);
    expect(FakeEventSource.instances).toHaveLength(SSE_MAX_RETRIES + 1);

    unsubscribe();
  });

  it("stops retrying once nobody is listening", () => {
    const unsubscribe = subscribeUserStream(vi.fn());
    FakeEventSource.instances[0].fail();
    unsubscribe();

    vi.advanceTimersByTime(SSE_BASE_BACKOFF_MS * 8);
    expect(FakeEventSource.instances).toHaveLength(1);
  });
});
