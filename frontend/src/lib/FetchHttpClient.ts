export interface HttpClient {
  get<T = any>(url: string, config?: RequestInit & { timeout?: number; signal?: AbortSignal }): Promise<T>;
  post<T = any, R = any>(url: string, data?: T, config?: RequestInit & { timeout?: number; signal?: AbortSignal }): Promise<R>;
  put<T = any, R = any>(url: string, data?: T, config?: RequestInit & { timeout?: number; signal?: AbortSignal }): Promise<R>;
  patch<T = any, R = any>(url: string, data?: T, config?: RequestInit & { timeout?: number; signal?: AbortSignal }): Promise<R>;
  delete<T = any>(url: string, config?: RequestInit & { timeout?: number; signal?: AbortSignal }): Promise<T>;
}

export class HttpError<T = any> extends Error {
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

export class FetchHttpClient implements HttpClient {
  private readonly baseURL: string;
  private isRefreshing = false;
  private refreshSubscribers: Array<() => void> = [];

  constructor(baseURL: string) {
    this.baseURL = baseURL;
  }

  private async request<T>(
    url: string,
    options: RequestInit & { _retry?: boolean; timeout?: number } = {}
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

      const csrfToken = this.getCookie("csrf_access");
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
          this.redirectToLogin();
        }

        const errorBody = await this.safeJson(response);

        console.log("errorBody: ", errorBody)
        throw new HttpError(
          errorBody?.error?.message || `An error occurred`,
          url,
          errorBody?.error?.code,
          errorBody
        );
      }

      return this.safeJson(response);
    } catch (error: any) {
      if (error.name === "AbortError") {
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
      await this.refreshToken();
      this.notifySubscribers();
      return this.request<T>(url, options);
    } catch (err) {
      console.error("Token refresh failed:", err);
      this.redirectToLogin();
      return Promise.reject(err);
    }
  }

  private async refreshToken(): Promise<void> {
    if (this.isRefreshing) {
      return new Promise((resolve) => this.refreshSubscribers.push(resolve));
    }
    this.isRefreshing = true;
    try {
      await fetch(`/api/users/auth/sessions/current`, {
        method: "POST",
        credentials: "include",
      });
    } finally {
      this.isRefreshing = false;
    }
  }

  private notifySubscribers() {
    this.refreshSubscribers.forEach((cb) => cb());
    this.refreshSubscribers = [];
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

  private redirectToLogin() {
    if (typeof window !== "undefined") {
      const current = window.location.pathname + window.location.search;
      window.location.href = `/login?redirect=${encodeURIComponent(current)}`;
    }
  }

  private redirectToAccessDenied() {
    if (typeof window !== "undefined") {
      window.location.href = `/403`;
    }
  }

  private notifyNetworkError() {
    if (typeof window !== "undefined") {
      console.error("Network error. Please check your internet connection.");
      alert("Network error. Please check your internet connection.");
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

  private isLogout(response: Response, method: string): boolean{
    const logoutUrl = "/users/auth/sessions/current"

    return response.url.indexOf(logoutUrl) > 0 && method.toLocaleUpperCase() === "DELETE"
  }

  // --- HttpClient methods ---
  async get<T = any>(url: string, config?: RequestInit & { timeout?: number; signal?: AbortSignal }): Promise<T> {
    return this.request<T>(url, { ...config, method: "GET" });
  }

  async post<T = any, R = any>(url: string, data?: T, config?: RequestInit & { timeout?: number; signal?: AbortSignal }): Promise<R> {
    return this.request<R>(url, {
      ...config,
      method: "POST",
      body: this.prepareBody(data),
    });
  }

  async put<T = any, R = any>(url: string, data?: T, config?: RequestInit & { timeout?: number; signal?: AbortSignal }): Promise<R> {
    return this.request<R>(url, {
      ...config,
      method: "PUT",
      body: this.prepareBody(data),
    });
  }

  async patch<T = any, R = any>(url: string, data?: T, config?: RequestInit & { timeout?: number; signal?: AbortSignal }): Promise<R> {
    return this.request<R>(url, {
      ...config,
      method: "PATCH",
      body: this.prepareBody(data),
    });
  }

  async delete<T = any>(url: string, config?: RequestInit & { timeout?: number; signal?: AbortSignal }): Promise<T> {
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
