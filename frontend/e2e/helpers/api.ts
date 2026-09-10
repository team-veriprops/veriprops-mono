/**
 * Thin authenticated HTTP client for spec preconditions and teardown — the TypeScript
 * mirror of `backend/scripts/e2e/harness.py` (docs/uat-strategy.md §3).
 *
 * UAT asserts through the UI; this client exists only to *bootstrap* the state a scenario
 * starts from, so every spec is independently runnable rather than chained to an earlier
 * spec's UI actions. Never assert a business outcome with it — assert it in the browser.
 *
 * Requests go to the Next.js origin (`/api/*`), which proxies to the backend: no call
 * reaches the backend directly (root CLAUDE.md).
 */
import { APIRequestContext, request } from "@playwright/test";

import { API_PREFIX, BASE_URL } from "./env";

/** Backend envelope: every endpoint returns `SuccessResponse[T]`. */
interface SuccessResponse<T> {
  data: T;
}

/** The double-submit CSRF pair the backend enforces on cookie-authenticated mutations. */
const ACCESS_CSRF_COOKIE = "__Host-access_csrf_token";
const CSRF_HEADER = "X-CSRF-Token";

const MUTATING_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

export class ApiClient {
  constructor(private readonly context: APIRequestContext) {}

  /** The session cookies this client holds, in Playwright `storageState` form. */
  async storageState() {
    return this.context.storageState();
  }

  async dispose(): Promise<void> {
    await this.context.dispose();
  }

  /** GET returning the unwrapped `data` payload. */
  async get<T>(path: string, params?: Record<string, string | number | boolean>): Promise<T> {
    return this.send<T>("GET", path, undefined, params);
  }

  async post<T>(path: string, body?: unknown): Promise<T> {
    return this.send<T>("POST", path, body);
  }

  async put<T>(path: string, body?: unknown): Promise<T> {
    return this.send<T>("PUT", path, body);
  }

  async patch<T>(path: string, body?: unknown): Promise<T> {
    return this.send<T>("PATCH", path, body);
  }

  async delete<T>(path: string, body?: unknown): Promise<T> {
    return this.send<T>("DELETE", path, body);
  }

  /** Raw status of a call, for preconditions that expect a rejection (403/404/409). */
  async status(method: string, path: string, body?: unknown): Promise<number> {
    const response = await this.context.fetch(this.url(path), {
      method,
      headers: await this.headers(method),
      ...(body === undefined ? {} : { data: body }),
    });
    return response.status();
  }

  private async send<T>(
    method: string,
    path: string,
    body?: unknown,
    params?: Record<string, string | number | boolean>,
  ): Promise<T> {
    const response = await this.context.fetch(this.url(path), {
      method,
      headers: await this.headers(method),
      ...(params ? { params } : {}),
      ...(body === undefined ? {} : { data: body }),
    });
    if (!response.ok()) {
      throw new Error(
        `${method} ${path} → ${response.status()} ${response.statusText()}: ${(
          await response.text()
        ).slice(0, 400)}`,
      );
    }
    const payload = (await response.json()) as SuccessResponse<T>;
    return payload.data;
  }

  private url(path: string): string {
    return `${BASE_URL}${API_PREFIX}${path.startsWith("/") ? path : `/${path}`}`;
  }

  /**
   * Mutations need the access CSRF token echoed from its cookie into the header
   * (double-submit). Read it per call: it is reissued on login and on every refresh.
   */
  private async headers(method: string): Promise<Record<string, string>> {
    if (!MUTATING_METHODS.has(method.toUpperCase())) return {};
    const { cookies } = await this.context.storageState();
    const csrf = cookies.find((cookie) => cookie.name === ACCESS_CSRF_COOKIE);
    return csrf ? { [CSRF_HEADER]: csrf.value } : {};
  }
}

/** An unauthenticated client — public endpoints, signup funnels, `/dev/*`. */
export async function anonymousApi(): Promise<ApiClient> {
  // ignoreHTTPSErrors: the local dev server's TLS cert is self-signed (see env.ts).
  return new ApiClient(await request.newContext({ baseURL: BASE_URL, ignoreHTTPSErrors: true }));
}

/** A client authenticated as *email* by driving the real login endpoint. */
export async function api(email: string, password: string): Promise<ApiClient> {
  const client = await anonymousApi();
  await client.post("/users/auth/sessions", { email, password });
  return client;
}
