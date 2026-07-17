import { ROUTES, buildAuthUrl } from "./routes";
import {
  SESSION_REFRESH_BACKOFF_MS,
  SESSION_REFRESH_MAX_ATTEMPTS,
} from "./config/app";
import {
  publishExpired,
  publishReconnecting,
  publishRecovered,
} from "./sessionRecovery";
import type { AuthSession } from "@components/website/auth/models";

/**
 * Login target for a session that could not be recovered, or null when the
 * current page is already on the auth surface — redirecting there again would
 * nest ?redirect= params and loop full page loads (auth pages may legitimately
 * receive 401s from optional session-scoped queries).
 */
export function loginRedirectUrl(pathname: string, search: string): string | null {
  if (pathname === ROUTES.AUTH.GATE || pathname.startsWith(`${ROUTES.AUTH.GATE}/`)) {
    return null;
  }
  return buildAuthUrl(ROUTES.AUTH.LOGIN, { redirect: pathname + search });
}

export interface HttpClient {
  get<T = unknown>(url: string, config?: RequestInit & { timeout?: number; signal?: AbortSignal }): Promise<T>;
  getBlob(url: string, config?: RequestInit & { timeout?: number; signal?: AbortSignal }): Promise<Blob>;
  post<T = unknown, R = unknown>(url: string, data?: T, config?: RequestInit & { timeout?: number; signal?: AbortSignal }): Promise<R>;
  put<T = unknown, R = unknown>(url: string, data?: T, config?: RequestInit & { timeout?: number; signal?: AbortSignal }): Promise<R>;
  patch<T = unknown, R = unknown>(url: string, data?: T, config?: RequestInit & { timeout?: number; signal?: AbortSignal }): Promise<R>;
  delete<T = unknown>(url: string, config?: RequestInit & { timeout?: number; signal?: AbortSignal }): Promise<T>;
}

export class HttpError<T = unknown> extends Error {
  status?: string;
  url: string;
  body?: T;

  constructor(message: string, url: string, status?: string, body?: T) {
    super(message);
    this.name = "HttpError";
    this.url = url;
    this.status = status;
    this.body = body;
  }
}

/** Refresh-call failure, classified for the retry budget (transient vs definitive). */
class SessionRefreshError extends HttpError {
  readonly transient: boolean;

  constructor(url: string, status: number | undefined, transient: boolean) {
    super("Session refresh failed", url, status === undefined ? undefined : String(status));
    this.name = "SessionRefreshError";
    this.transient = transient;
  }
}

const delay = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

export class FetchHttpClient implements HttpClient {
  private readonly baseURL: string;
  /** Single-flight session refresh: concurrent 401s await the same promise. */
  private refreshPromise: Promise<void> | null = null;

  constructor(baseURL: string) {
    this.baseURL = baseURL;
  }

  private async request<T>(
    url: string,
    options: RequestInit & { _retry?: boolean; timeout?: number; _responseType?: 'blob' } = {}
  ): Promise<T> {
    const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
    };

    // Content-Type if not FormData/Blob
    if (
      !(options.body instanceof FormData) &&
      !(options.body instanceof Blob) &&
      !(options.body instanceof ArrayBuffer)
    ) {
      headers["Content-Type"] = "application/json";
    }

    // Context headers
    if (typeof window !== "undefined") {
      const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
      const locale = navigator.language || "en-US";
      headers["X-TIMEZONE"] = timezone;
      headers["X-LOCALE"] = locale;

      const csrfToken = this.getCookie("__Host-access_csrf_token");
      if (csrfToken) {
        headers["X-CSRF-Token"] = csrfToken;
      }
    }

    // Timeout & cancellation
    const controller = new AbortController();
    const signals: AbortSignal[] = [controller.signal];
    if (options.signal) signals.push(options.signal);

    const timeoutId = options.timeout
      ? setTimeout(() => controller.abort(), options.timeout)
      : null;

    try {
      const response = await fetch(this.baseURL + url, {
        ...options,
        headers,
        signal: signals.length > 1 ? this.mergeSignals(signals) : signals[0],
        credentials: "include",
      });

      if (!response.ok) {
        if (response.status === 401 && !options._retry) {
          return this.handle401<T>(url, options);
        }
        if (response.status === 403) {
          this.redirectToAccessDenied();
        }
        if (response.status === 419) {
          // Authentication-timeout: unrecoverable by refresh — hand the user
          // to the SessionRecoveryOverlay's expired state.
          this.publishSessionExpired();
        }

        const errorBody = await this.safeJson(response);

        throw new HttpError(
          errorBody?.error?.message || `An error occurred`,
          url,
          errorBody?.error?.code,
          errorBody
        );
      }

      if (options._responseType === 'blob') {
        return response.blob() as unknown as T;
      }
      return this.safeJson(response);
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        throw new HttpError("Request aborted (timeout or manual cancel)", url);
      }
      if (error instanceof TypeError) {
        this.notifyNetworkError();
        throw new HttpError("Network error", url);
      }
      throw error;
    } finally {
      if (timeoutId) clearTimeout(timeoutId);
    }
  }

  private async handle401<T>(
    url: string,
    options: RequestInit & { _retry?: boolean }
  ): Promise<T> {
    options._retry = true;

    try {
      await this.refreshSession();
      return this.request<T>(url, options);
    } catch (err) {
      // Status only — never log response bodies (may carry PII/internal detail).
      // Navigation is owned by SessionRecoveryOverlay via the expired phase
      // published inside the refresh loop.
      console.error(
        "Session refresh failed",
        err instanceof HttpError ? `(status ${err.status})` : ""
      );
      return Promise.reject(err);
    }
  }

  /**
   * Single-flight session refresh with a transient-failure retry budget.
   * Public so the proactive keep-alive hook can renew the session before the
   * access token expires; concurrent 401s and the keep-alive all share one
   * in-flight recovery.
   */
  refreshSession(): Promise<void> {
    if (!this.refreshPromise) {
      this.refreshPromise = this.runRefreshWithRetries().finally(() => {
        this.refreshPromise = null;
      });
    }
    return this.refreshPromise;
  }

  /**
   * Attempt 1 is silent (routine refreshes must not flash recovery UI). Each
   * *transient* failure (network / 5xx) publishes a reconnecting attempt for
   * the overlay and backs off before retrying; a *definitive* rejection
   * (401/403/419 — the session is dead) or an exhausted budget publishes the
   * expired phase, whose overlay performs the login handoff.
   */
  private async runRefreshWithRetries(): Promise<void> {
    for (let attempt = 1; attempt <= SESSION_REFRESH_MAX_ATTEMPTS; attempt++) {
      try {
        const session = await this.performRefresh();
        publishRecovered(session);
        return;
      } catch (err) {
        const transient = err instanceof SessionRefreshError && err.transient;
        if (!transient || attempt === SESSION_REFRESH_MAX_ATTEMPTS) {
          this.publishSessionExpired();
          throw err;
        }
        publishReconnecting(attempt + 1, SESSION_REFRESH_MAX_ATTEMPTS);
        await delay(SESSION_REFRESH_BACKOFF_MS * 2 ** (attempt - 1));
      }
    }
  }

  private async performRefresh(): Promise<AuthSession | null> {
    // The HttpOnly refresh cookie rides along via credentials: "include";
    // only its non-HttpOnly CSRF twin must be copied into the header
    // (double-submit pattern). Never reuse the failed request's headers —
    // they carry the ACCESS csrf token, which the refresh endpoint rejects.
    const headers: Record<string, string> = {};
    const refreshCsrf = this.getCookie("__Host-refresh_csrf_token");
    if (refreshCsrf) {
      headers["X-CSRF-Token"] = refreshCsrf;
    }

    const refreshPath = "/users/auth/sessions/current";
    let response: Response;
    try {
      response = await fetch(this.baseURL + refreshPath, {
        method: "POST",
        headers,
        credentials: "include",
      });
    } catch {
      throw new SessionRefreshError(refreshPath, undefined, true);
    }
    if (!response.ok) {
      const definitive =
        response.status === 401 || response.status === 403 || response.status === 419;
      throw new SessionRefreshError(refreshPath, response.status, !definitive);
    }
    // The endpoint returns the session DTO so the keep-alive can reschedule
    // from the fresh accessTokenExpiresAt.
    const body = await this.safeJson(response);
    return (body?.data as AuthSession | undefined) ?? null;
  }

  private publishSessionExpired() {
    if (typeof window === "undefined") return;
    publishExpired(loginRedirectUrl(window.location.pathname, window.location.search));
  }

  private async safeJson(response: Response) {
    try {
      return await response.json();
    } catch {
      return null;
    }
  }

  private getCookie(name: string): string | null {
    if (typeof document === "undefined") return null;
    const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
    return match ? decodeURIComponent(match[1]) : null;
  }

  private redirectToAccessDenied() {
    if (typeof window !== "undefined") {
      window.location.href = ROUTES.FORBIDDEN;
    }
  }

  private notifyNetworkError() {
    if (typeof window !== "undefined") {
      console.error("Network error. Please check your internet connection.");
    }
  }

  private mergeSignals(signals: AbortSignal[]): AbortSignal {
    const controller = new AbortController();
    signals.forEach((sig) => {
      if (sig.aborted) controller.abort();
      else sig.addEventListener("abort", () => controller.abort());
    });
    return controller.signal;
  }

  // --- HttpClient methods ---
  async get<T = unknown>(url: string, config?: RequestInit & { timeout?: number; signal?: AbortSignal }): Promise<T> {
    return this.request<T>(url, { ...config, method: "GET" });
  }

  async getBlob(url: string, config?: RequestInit & { timeout?: number; signal?: AbortSignal }): Promise<Blob> {
    return this.request<Blob>(url, { ...config, method: "GET", _responseType: "blob" });
  }

  async post<T = unknown, R = unknown>(url: string, data?: T, config?: RequestInit & { timeout?: number; signal?: AbortSignal }): Promise<R> {
    return this.request<R>(url, {
      ...config,
      method: "POST",
      body: this.prepareBody(data),
    });
  }

  async put<T = unknown, R = unknown>(url: string, data?: T, config?: RequestInit & { timeout?: number; signal?: AbortSignal }): Promise<R> {
    return this.request<R>(url, {
      ...config,
      method: "PUT",
      body: this.prepareBody(data),
    });
  }

  async patch<T = unknown, R = unknown>(url: string, data?: T, config?: RequestInit & { timeout?: number; signal?: AbortSignal }): Promise<R> {
    return this.request<R>(url, {
      ...config,
      method: "PATCH",
      body: this.prepareBody(data),
    });
  }

  async delete<T = unknown>(url: string, config?: RequestInit & { timeout?: number; signal?: AbortSignal }): Promise<T> {
    return this.request<T>(url, { ...config, method: "DELETE" });
  }

  private prepareBody<T>(data?: T): BodyInit | undefined {
    if (!data) return undefined;
    if (data instanceof FormData || data instanceof Blob || data instanceof ArrayBuffer) {
      return data as BodyInit;
    }
    if (typeof data === "string") return data;
    return JSON.stringify(data); // default JSON
  }
}
