// ─────────────────────────────────────────────────────────────────────────────
// core/api-runner.ts
// Stateful HTTP client for API-mode journeys.
// Maintains a cookie jar per session so auth tokens persist across steps.
// ─────────────────────────────────────────────────────────────────────────────

import type { APIRequestOptions, APIResponse, QAConfig } from "./types.js";

export class APIRunner {
  private cookieJar: Map<string, string> = new Map();
  private config: QAConfig;

  constructor(config: QAConfig) {
    this.config = config;
  }

  // ─── Public interface ──────────────────────────────────────────────────────

  async get<T = unknown>(
    path: string,
    headers?: Record<string, string>
  ): Promise<APIResponse<T>> {
    return this.call<T>({ method: "GET", path, headers });
  }

  async post<T = unknown>(
    path: string,
    body?: unknown,
    headers?: Record<string, string>
  ): Promise<APIResponse<T>> {
    return this.call<T>({ method: "POST", path, body, headers });
  }

  async put<T = unknown>(
    path: string,
    body?: unknown,
    headers?: Record<string, string>
  ): Promise<APIResponse<T>> {
    return this.call<T>({ method: "PUT", path, body, headers });
  }

  async patch<T = unknown>(
    path: string,
    body?: unknown,
    headers?: Record<string, string>
  ): Promise<APIResponse<T>> {
    return this.call<T>({ method: "PATCH", path, body, headers });
  }

  async delete<T = unknown>(
    path: string,
    headers?: Record<string, string>
  ): Promise<APIResponse<T>> {
    return this.call<T>({ method: "DELETE", path, headers });
  }

  // ─── Core call ────────────────────────────────────────────────────────────

  async call<T = unknown>(options: APIRequestOptions): Promise<APIResponse<T>> {
    const url = this.resolveUrl(options.path);
    const cookieHeader = this.buildCookieHeader();

    const response = await fetch(url, {
      method: options.method,
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        ...(cookieHeader ? { Cookie: cookieHeader } : {}),
        ...options.headers,
      },
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
      signal: AbortSignal.timeout(this.config.timeout),
    });

    // Persist any Set-Cookie headers from the response
    this.persistCookies(response.headers);

    const responseHeaders: Record<string, string> = {};
    response.headers.forEach((value, key) => {
      responseHeaders[key] = value;
    });

    let body: T;
    if (options.rawResponse) {
      body = (await response.text()) as unknown as T;
    } else {
      const text = await response.text();
      try {
        body = text.length > 0 ? (JSON.parse(text) as T) : ({} as T);
      } catch {
        body = text as unknown as T;
      }
    }

    return {
      status: response.status,
      headers: responseHeaders,
      body,
      ok: response.ok,
    };
  }

  // ─── Session helpers ──────────────────────────────────────────────────────

  /** Manually set a cookie (e.g. after login extracts a token). */
  setCookie(name: string, value: string): void {
    this.cookieJar.set(name, value);
  }

  /** Returns the current cookie jar as a plain object. */
  getCookies(): Record<string, string> {
    return Object.fromEntries(this.cookieJar);
  }

  /** Clears all stored cookies. Call between sessions. */
  clearCookies(): void {
    this.cookieJar.clear();
  }

  // ─── Internals ────────────────────────────────────────────────────────────

  private resolveUrl(pathOrUrl: string): string {
    if (pathOrUrl.startsWith("http://") || pathOrUrl.startsWith("https://")) {
      return pathOrUrl;
    }
    const base = this.config.apiBaseUrl.replace(/\/$/, "");
    const suffix = pathOrUrl.startsWith("/") ? pathOrUrl : `/${pathOrUrl}`;
    return `${base}${suffix}`;
  }

  private buildCookieHeader(): string {
    if (this.cookieJar.size === 0) return "";
    return [...this.cookieJar.entries()]
      .map(([k, v]) => `${k}=${v}`)
      .join("; ");
  }

  private persistCookies(headers: Headers): void {
    // Node fetch exposes Set-Cookie as a single string in some environments.
    // We handle both single and multi-value forms.
    const raw = headers.get("set-cookie");
    if (!raw) return;

    // Split on ", " only when it precedes a cookie name (heuristic)
    const cookies = raw.split(/,(?=[^ ])/);
    for (const cookie of cookies) {
      const [nameValue] = cookie.split(";");
      if (!nameValue) continue;
      const eqIndex = nameValue.indexOf("=");
      if (eqIndex === -1) continue;
      const name = nameValue.slice(0, eqIndex).trim();
      const value = nameValue.slice(eqIndex + 1).trim();
      if (name) this.cookieJar.set(name, value);
    }
  }
}
