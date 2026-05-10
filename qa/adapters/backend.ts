// ─────────────────────────────────────────────────────────────────────────────
// adapters/backend.ts
// HTTP client for backend dev/test endpoints.
// Handles reset, seed, bootstrap, and data snapshot operations.
// storage.ts has been merged here — snapshot() lives on BackendAdapter.
// ─────────────────────────────────────────────────────────────────────────────

import type { QAConfig } from "../core/types.js";

export class BackendAdapter {
  private config: QAConfig;

  constructor(config: QAConfig) {
    this.config = config;
  }

  // ─── Core call ────────────────────────────────────────────────────────────

  async call<T = unknown>(
    method: "GET" | "POST" | "PUT" | "DELETE",
    path: string,
    body?: unknown
  ): Promise<T> {
    const url = `${this.config.apiBaseUrl.replace(/\/$/, "")}${path}`;

    const response = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json" },
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: AbortSignal.timeout(this.config.timeout),
    });

    if (!response.ok) {
      const text = await response.text().catch(() => "(no body)");
      throw new Error(
        `BackendAdapter ${method} ${path} failed: ${response.status} ${response.statusText} — ${text}`
      );
    }

    const text = await response.text();
    if (!text) return undefined as unknown as T;

    try {
      return JSON.parse(text) as T;
    } catch {
      return text as unknown as T;
    }
  }

  // ─── Standard lifecycle endpoints ─────────────────────────────────────────

  /**
   * Resets the database to a clean baseline state.
   * Maps to POST /qa/reset (or equivalent on your backend).
   */
  async reset(): Promise<void> {
    await this.call("POST", "/qa/reset");
  }

  /**
   * Seeds reference/fixture data required for tests.
   * Maps to POST /qa/seed with optional payload.
   */
  async seed(payload?: Record<string, unknown>): Promise<void> {
    await this.call("POST", "/qa/seed", payload);
  }

  /**
   * General-purpose bootstrap dispatcher.
   * Resolves action names to backend endpoints.
   * Domain bootstrap steps call this with their declared action string.
   */
  async bootstrap(action: string, payload?: Record<string, unknown>): Promise<void> {
    switch (action) {
      case "reset":
        await this.reset();
        break;
      case "seed":
        await this.seed(payload);
        break;
      case "bootstrap":
        await this.call("POST", "/qa/bootstrap", payload);
        break;
      default:
        // Custom action — POST to /qa/<action>
        await this.call("POST", `/qa/${action}`, payload);
    }
  }

  // ─── Snapshot (merged from storage.ts) ───────────────────────────────────

  /**
   * Fetches a serialised snapshot of the current backend state.
   * Useful for before/after comparisons in assertions.
   * Maps to GET /qa/snapshot or GET /qa/snapshot/<resource>.
   */
  async snapshot<T = unknown>(resource?: string): Promise<T> {
    const path = resource ? `/qa/snapshot/${resource}` : "/qa/snapshot";
    return this.call<T>("GET", path);
  }

  /**
   * Serialises an in-memory value to JSON string.
   * Convenience helper for state assertions.
   */
  serialise(value: unknown): string {
    return JSON.stringify(value, null, 2);
  }

  /**
   * Parses a JSON string back to a typed value.
   */
  deserialise<T = unknown>(json: string): T {
    return JSON.parse(json) as T;
  }

  // ─── Health check ─────────────────────────────────────────────────────────

  /**
   * Pings the backend health endpoint.
   * Returns true if reachable, false otherwise (never throws).
   */
  async isReachable(): Promise<boolean> {
    try {
      const response = await fetch(
        `${this.config.apiBaseUrl.replace(/\/$/, "")}/health`,
        { signal: AbortSignal.timeout(5000) }
      );
      return response.ok;
    } catch {
      return false;
    }
  }
}
