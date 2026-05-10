// ─────────────────────────────────────────────────────────────────────────────
// core/event-bus.ts
// Lightweight typed event emitter for QA platform observability.
// The orchestrator emits. The CLI and logger subscribe.
// Future consumers (webhooks, Slack) subscribe without touching core.
// ─────────────────────────────────────────────────────────────────────────────

import type { QAEvent, QAEventType, QAEventPayload } from "./types.js";

type EventHandler<T extends QAEventType> = (event: QAEvent<T>) => void | Promise<void>;

class QAEventBus {
  private handlers = new Map<QAEventType, Set<EventHandler<QAEventType>>>();

  on<T extends QAEventType>(type: T, handler: EventHandler<T>): () => void {
    if (!this.handlers.has(type)) {
      this.handlers.set(type, new Set());
    }
    const set = this.handlers.get(type)!;
    set.add(handler as EventHandler<QAEventType>);

    // Return unsubscribe function
    return () => set.delete(handler as EventHandler<QAEventType>);
  }

  async emit<T extends QAEventType>(type: T, payload: QAEventPayload[T]): Promise<void> {
    const event: QAEvent<T> = {
      type,
      timestamp: new Date().toISOString(),
      payload,
    };

    const set = this.handlers.get(type);
    if (!set || set.size === 0) return;

    const promises: Promise<void>[] = [];
    for (const handler of set) {
      try {
        const result = (handler as EventHandler<T>)(event);
        if (result instanceof Promise) promises.push(result);
      } catch (err) {
        // Event bus errors are non-fatal — log and continue
        console.error(`[event-bus] Handler error for "${type}":`, err);
      }
    }

    if (promises.length > 0) {
      await Promise.allSettled(promises);
    }
  }

  /** Remove all handlers for all event types. Useful between test runs. */
  clear(): void {
    this.handlers.clear();
  }

  /** Remove all handlers for a specific event type. */
  off(type: QAEventType): void {
    this.handlers.delete(type);
  }
}

/** Singleton event bus. Import and use throughout the platform. */
export const eventBus = new QAEventBus();
