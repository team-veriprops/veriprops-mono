import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { FetchHttpClient, HttpError, loginRedirectUrl } from "./FetchHttpClient";

const API = "/api";
const REFRESH_URL = `${API}/users/auth/sessions/current`;
const ACCESS_CSRF = "access-csrf-value";
const REFRESH_CSRF = "refresh-csrf-value";

// jsdom forbids replacing window.location, so navigation is asserted on the
// client's redirect helpers instead of on location.href.
type RedirectSpies = { toLogin: ReturnType<typeof vi.spyOn>; toAccessDenied: ReturnType<typeof vi.spyOn> };
function spyOnRedirects(): RedirectSpies {
  const proto = FetchHttpClient.prototype as unknown as {
    redirectToLogin(): void;
    redirectToAccessDenied(): void;
  };
  return {
    toLogin: vi.spyOn(proto, "redirectToLogin").mockImplementation(() => {}),
    toAccessDenied: vi.spyOn(proto, "redirectToAccessDenied").mockImplementation(() => {}),
  };
}

const res = (status: number, body?: unknown) =>
  new Response(body === undefined ? null : JSON.stringify(body), { status });

const unauthorized = () => res(401, { error: { code: "401", message: "Signature has expired" } });

type FetchCall = { url: string; init: RequestInit };
let fetchCalls: FetchCall[];
let fetchMock: ReturnType<typeof vi.fn>;

const isRefreshCall = (call: FetchCall) =>
  call.url === REFRESH_URL && call.init.method === "POST";

const refreshCalls = () => fetchCalls.filter(isRefreshCall);

/**
 * Installs a fetch stub that answers the refresh POST with `refresh` responses
 * (in order, last one repeating) and every other request with `original`
 * responses (in order, last one repeating).
 */
function stubFetch({ original, refresh }: { original: Array<() => Response>; refresh: Array<() => Response> }) {
  let originalIdx = 0;
  let refreshIdx = 0;
  fetchMock = vi.fn(async (url: string, init: RequestInit = {}) => {
    const call = { url, init };
    fetchCalls.push(call);
    if (isRefreshCall(call)) {
      const make = refresh[Math.min(refreshIdx++, refresh.length - 1)];
      return make();
    }
    const make = original[Math.min(originalIdx++, original.length - 1)];
    return make();
  });
  vi.stubGlobal("fetch", fetchMock);
}

let redirects: RedirectSpies;
let client: FetchHttpClient;

beforeEach(() => {
  fetchCalls = [];
  redirects = spyOnRedirects();
  vi.spyOn(document, "cookie", "get").mockReturnValue(
    `__Host-access_csrf_token=${ACCESS_CSRF}; __Host-refresh_csrf_token=${REFRESH_CSRF}`
  );
  vi.spyOn(console, "error").mockImplementation(() => {});
  client = new FetchHttpClient(API);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("401 → refresh → retry", () => {
  it("refreshes the session once and retries the original request", async () => {
    stubFetch({
      original: [() => unauthorized(), () => res(200, { data: "fresh" })],
      refresh: [() => res(200)],
    });

    const result = await client.get<{ data: string }>("/things");

    expect(result).toEqual({ data: "fresh" });
    // original → refresh → retried original
    expect(fetchCalls.map((c) => c.url)).toEqual([`${API}/things`, REFRESH_URL, `${API}/things`]);
    expect(redirects.toLogin).not.toHaveBeenCalled();
  });

  it("sends the REFRESH csrf token (not the access one) and no request-body headers on the refresh call", async () => {
    stubFetch({
      original: [() => unauthorized(), () => res(200, { ok: true })],
      refresh: [() => res(200)],
    });

    await client.post("/things", { name: "x" });

    const [refreshCall] = refreshCalls();
    expect(refreshCall).toBeDefined();
    const headers = refreshCall.init.headers as Record<string, string>;
    expect(headers["X-CSRF-Token"]).toBe(REFRESH_CSRF);
    expect(headers["Content-Type"]).toBeUndefined();
    expect(refreshCall.init.credentials).toBe("include");
    expect(refreshCall.init.body).toBeUndefined();
  });
});

describe("failed refresh", () => {
  it("rejects and redirects to login when the refresh endpoint returns 401", async () => {
    stubFetch({
      original: [() => unauthorized()],
      refresh: [() => res(401, { error: { code: "401", message: "Session has been revoked" } })],
    });

    await expect(client.get("/things")).rejects.toBeInstanceOf(HttpError);
    expect(redirects.toLogin).toHaveBeenCalled();
    // The dead original request must not be retried after a failed refresh.
    expect(fetchCalls.map((c) => c.url)).toEqual([`${API}/things`, REFRESH_URL]);
  });

  it("rejects and redirects to login when the refresh call fails at the network level", async () => {
    fetchMock = vi.fn(async (url: string, init: RequestInit = {}) => {
      const call = { url, init };
      fetchCalls.push(call);
      if (isRefreshCall(call)) throw new TypeError("Failed to fetch");
      return unauthorized();
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(client.get("/things")).rejects.toBeInstanceOf(Error);
    expect(redirects.toLogin).toHaveBeenCalled();
  });

  it("does not refresh again when the retried request still returns 401", async () => {
    stubFetch({
      original: [() => unauthorized(), () => unauthorized()],
      refresh: [() => res(200)],
    });

    await expect(client.get("/things")).rejects.toBeInstanceOf(HttpError);
    expect(refreshCalls()).toHaveLength(1);
  });
});

describe("concurrent 401s share a single refresh", () => {
  it("issues exactly one refresh POST for parallel failing requests, then retries both", async () => {
    stubFetch({
      original: [() => unauthorized(), () => unauthorized(), () => res(200, { ok: true })],
      refresh: [() => res(200)],
    });

    const [a, b] = await Promise.all([client.get("/a"), client.get("/b")]);

    expect(a).toEqual({ ok: true });
    expect(b).toEqual({ ok: true });
    expect(refreshCalls()).toHaveLength(1);
  });

  it("rejects every waiter (no hung promises) when the shared refresh fails", async () => {
    stubFetch({
      original: [() => unauthorized()],
      refresh: [() => res(401)],
    });

    const results = await Promise.allSettled([client.get("/a"), client.get("/b")]);

    expect(results.map((r) => r.status)).toEqual(["rejected", "rejected"]);
    expect(refreshCalls()).toHaveLength(1);
    expect(redirects.toLogin).toHaveBeenCalled();
  });
});

describe("loginRedirectUrl", () => {
  it("targets login with the current path+query as the redirect param", () => {
    expect(loginRedirectUrl("/portal/dashboard", "?tab=recent")).toBe(
      `/auth/login?redirect=${encodeURIComponent("/portal/dashboard?tab=recent")}`
    );
  });

  it("returns null on auth routes so a failed refresh cannot loop the login page", () => {
    expect(loginRedirectUrl("/auth", "")).toBeNull();
    expect(loginRedirectUrl("/auth/login", "?redirect=%2Fportal%2Fdashboard")).toBeNull();
    expect(loginRedirectUrl("/auth/signup", "")).toBeNull();
  });

  it("does not treat non-auth prefixes as auth routes", () => {
    expect(loginRedirectUrl("/authors", "")).not.toBeNull();
  });
});

describe("non-401 statuses are untouched by the refresh path", () => {
  it("403 → access-denied redirect, no refresh attempt", async () => {
    stubFetch({ original: [() => res(403, { error: { code: "403", message: "Forbidden" } })], refresh: [] });

    await expect(client.get("/things")).rejects.toBeInstanceOf(HttpError);
    expect(redirects.toAccessDenied).toHaveBeenCalled();
    expect(refreshCalls()).toHaveLength(0);
  });

  it("419 → login redirect, no refresh attempt", async () => {
    stubFetch({ original: [() => res(419, { error: { code: "419", message: "Session expired" } })], refresh: [] });

    await expect(client.get("/things")).rejects.toBeInstanceOf(HttpError);
    expect(redirects.toLogin).toHaveBeenCalled();
    expect(refreshCalls()).toHaveLength(0);
  });

  it("500 → plain HttpError, no refresh attempt", async () => {
    stubFetch({ original: [() => res(500, { error: { code: "500", message: "boom" } })], refresh: [] });

    await expect(client.get("/things")).rejects.toBeInstanceOf(HttpError);
    expect(refreshCalls()).toHaveLength(0);
    expect(redirects.toLogin).not.toHaveBeenCalled();
    expect(redirects.toAccessDenied).not.toHaveBeenCalled();
  });
});
