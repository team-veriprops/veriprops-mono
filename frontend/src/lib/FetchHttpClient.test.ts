import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { FetchHttpClient, HttpError, loginRedirectUrl } from "./FetchHttpClient";
import {
  consumeRefreshedSession,
  publishExpired,
  resetSessionRecovery,
  sessionRecoveryStore,
  type SessionRecoveryPhase,
} from "./sessionRecovery";
import {
  SESSION_REFRESH_BACKOFF_MS,
  SESSION_REFRESH_MAX_ATTEMPTS,
} from "./config/app";

const API = "/api";
const REFRESH_URL = `${API}/users/auth/sessions/current`;
const ACCESS_CSRF = "access-csrf-value";
const REFRESH_CSRF = "refresh-csrf-value";

/** Minimal session DTO as the refresh endpoint now returns it. */
const SESSION_DTO = {
  accessTokenExpiresAt: "2026-07-17T13:00:00Z",
  refreshTokenExpiresAt: "2026-08-16T12:00:00Z",
  user: { id: "u1" },
};

// jsdom forbids replacing window.location, so the 403 navigation is asserted on
// the client's redirect helper; session expiry no longer navigates directly —
// it publishes to sessionRecoveryStore, which is asserted on instead.
function spyOnAccessDeniedRedirect() {
  const proto = FetchHttpClient.prototype as unknown as { redirectToAccessDenied(): void };
  return vi.spyOn(proto, "redirectToAccessDenied").mockImplementation(() => {});
}

const res = (status: number, body?: unknown) =>
  new Response(body === undefined ? null : JSON.stringify(body), { status });

const unauthorized = () => res(401, { error: { code: "401", message: "Signature has expired" } });
const refreshOk = () => res(200, { data: SESSION_DTO });

type FetchCall = { url: string; init: RequestInit };
let fetchCalls: FetchCall[];
let fetchMock: ReturnType<typeof vi.fn>;

const isRefreshCall = (call: FetchCall) =>
  call.url === REFRESH_URL && call.init.method === "POST";

const refreshCalls = () => fetchCalls.filter(isRefreshCall);

const phase = () => sessionRecoveryStore.getState().phase;

/** Record every phase transition for asserting intermediate states. */
function recordPhases(): SessionRecoveryPhase[] {
  const seen: SessionRecoveryPhase[] = [];
  sessionRecoveryStore.subscribe((state, prev) => {
    if (state.phase !== prev.phase) seen.push(state.phase);
  });
  return seen;
}

/**
 * Installs a fetch stub that answers the refresh POST with `refresh` responses
 * (in order, last one repeating) and every other request with `original`
 * responses (in order, last one repeating). A refresh entry may throw to
 * simulate a network-level failure.
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

/** Resolve a promise that may be gated on fake backoff timers. */
async function settleWithTimers<T>(p: Promise<T>): Promise<PromiseSettledResult<T>> {
  const guarded = p.then(
    (value) => ({ status: "fulfilled", value }) as const,
    (reason) => ({ status: "rejected", reason }) as const,
  );
  await vi.runAllTimersAsync();
  return guarded;
}

let accessDenied: ReturnType<typeof spyOnAccessDeniedRedirect>;
let client: FetchHttpClient;

beforeEach(() => {
  fetchCalls = [];
  resetSessionRecovery();
  accessDenied = spyOnAccessDeniedRedirect();
  vi.spyOn(document, "cookie", "get").mockReturnValue(
    `__Host-access_csrf_token=${ACCESS_CSRF}; __Host-refresh_csrf_token=${REFRESH_CSRF}`
  );
  vi.spyOn(console, "error").mockImplementation(() => {});
  client = new FetchHttpClient(API);
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("401 → refresh → retry (happy path stays invisible)", () => {
  it("refreshes the session once, retries the original request, and never leaves idle", async () => {
    const phases = recordPhases();
    stubFetch({
      original: [() => unauthorized(), () => res(200, { data: "fresh" })],
      refresh: [refreshOk],
    });

    const result = await client.get<{ data: string }>("/things");

    expect(result).toEqual({ data: "fresh" });
    // original → refresh → retried original
    expect(fetchCalls.map((c) => c.url)).toEqual([`${API}/things`, REFRESH_URL, `${API}/things`]);
    expect(phases).toEqual([]); // a routine one-shot refresh must not flash the overlay
    expect(phase()).toBe("idle");
  });

  it("publishes the refreshed session DTO for the React bridge to store", async () => {
    stubFetch({
      original: [() => unauthorized(), () => res(200, { ok: true })],
      refresh: [refreshOk],
    });

    await client.get("/things");

    expect(consumeRefreshedSession()).toEqual(SESSION_DTO);
    expect(consumeRefreshedSession()).toBeNull(); // consumed once
  });

  it("sends the REFRESH csrf token (not the access one) and no request-body headers on the refresh call", async () => {
    stubFetch({
      original: [() => unauthorized(), () => res(200, { ok: true })],
      refresh: [refreshOk],
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

describe("definitive refresh rejections are not retried", () => {
  it("401 from the refresh endpoint → single attempt, expired phase with a login target", async () => {
    stubFetch({
      original: [() => unauthorized()],
      refresh: [() => res(401, { error: { code: "401", message: "Session has been revoked" } })],
    });

    await expect(client.get("/things")).rejects.toBeInstanceOf(HttpError);
    expect(refreshCalls()).toHaveLength(1);
    // The dead original request must not be retried after a failed refresh.
    expect(fetchCalls.map((c) => c.url)).toEqual([`${API}/things`, REFRESH_URL]);
    const state = sessionRecoveryStore.getState();
    expect(state.phase).toBe("expired");
    expect(state.redirectTo).toContain("/auth/login?redirect=");
  });

  it("419 on any request → expired phase without a refresh attempt", async () => {
    stubFetch({ original: [() => res(419, { error: { code: "419", message: "Session expired" } })], refresh: [] });

    await expect(client.get("/things")).rejects.toBeInstanceOf(HttpError);
    expect(refreshCalls()).toHaveLength(0);
    expect(phase()).toBe("expired");
  });
});

describe("transient refresh failures use the retry budget", () => {
  it("retries a network-failing refresh up to the budget with doubling backoff, then expires", async () => {
    vi.useFakeTimers();
    fetchMock = vi.fn(async (url: string, init: RequestInit = {}) => {
      const call = { url, init };
      fetchCalls.push(call);
      if (isRefreshCall(call)) throw new TypeError("Failed to fetch");
      return unauthorized();
    });
    vi.stubGlobal("fetch", fetchMock);

    const settled = await settleWithTimers(client.get("/things"));

    expect(settled.status).toBe("rejected");
    expect(refreshCalls()).toHaveLength(SESSION_REFRESH_MAX_ATTEMPTS);
    expect(phase()).toBe("expired");
  });

  it("does not fire a retry before its backoff delay has elapsed", async () => {
    vi.useFakeTimers();
    stubFetch({ original: [() => unauthorized()], refresh: [() => res(503)] });

    const pending = client.get("/things").catch(() => undefined);
    await vi.advanceTimersByTimeAsync(0);
    expect(refreshCalls()).toHaveLength(1); // attempt 1 failed, retry waiting on backoff

    await vi.advanceTimersByTimeAsync(SESSION_REFRESH_BACKOFF_MS - 1);
    expect(refreshCalls()).toHaveLength(1);

    await vi.advanceTimersByTimeAsync(1);
    expect(refreshCalls()).toHaveLength(2);
    await vi.runAllTimersAsync();
    await pending;
  });

  it("publishes reconnecting attempts for the overlay while retrying", async () => {
    vi.useFakeTimers();
    const attempts: number[] = [];
    sessionRecoveryStore.subscribe((state, prev) => {
      if (state.phase === "reconnecting" && state.attempt !== prev.attempt) attempts.push(state.attempt);
    });
    stubFetch({ original: [() => unauthorized()], refresh: [() => res(503)] });

    await settleWithTimers(client.get("/things"));

    expect(attempts).toEqual([2, 3]);
    expect(sessionRecoveryStore.getState().maxAttempts).toBe(SESSION_REFRESH_MAX_ATTEMPTS);
    expect(phase()).toBe("expired");
  });

  it("recovers mid-budget: a 5xx then a success closes recovery and retries the original", async () => {
    vi.useFakeTimers();
    const phases = recordPhases();
    stubFetch({
      original: [() => unauthorized(), () => res(200, { data: "fresh" })],
      refresh: [() => res(503), refreshOk],
    });

    const settled = await settleWithTimers(client.get<{ data: string }>("/things"));

    expect(settled).toEqual({ status: "fulfilled", value: { data: "fresh" } });
    expect(refreshCalls()).toHaveLength(2);
    expect(phases).toEqual(["reconnecting", "idle"]);
    expect(consumeRefreshedSession()).toEqual(SESSION_DTO);
  });
});

describe("retry loop guard", () => {
  it("does not refresh again when the retried request still returns 401", async () => {
    stubFetch({
      original: [() => unauthorized(), () => unauthorized()],
      refresh: [refreshOk],
    });

    await expect(client.get("/things")).rejects.toBeInstanceOf(HttpError);
    expect(refreshCalls()).toHaveLength(1);
  });
});

describe("concurrent 401s share a single refresh", () => {
  it("issues exactly one refresh POST for parallel failing requests, then retries both", async () => {
    stubFetch({
      original: [() => unauthorized(), () => unauthorized(), () => res(200, { ok: true })],
      refresh: [refreshOk],
    });

    const [a, b] = await Promise.all([client.get("/a"), client.get("/b")]);

    expect(a).toEqual({ ok: true });
    expect(b).toEqual({ ok: true });
    expect(refreshCalls()).toHaveLength(1);
  });

  it("rejects every waiter (no hung promises) when the shared refresh definitively fails", async () => {
    stubFetch({
      original: [() => unauthorized()],
      refresh: [() => res(401)],
    });

    const results = await Promise.allSettled([client.get("/a"), client.get("/b")]);

    expect(results.map((r) => r.status)).toEqual(["rejected", "rejected"]);
    expect(refreshCalls()).toHaveLength(1);
    expect(phase()).toBe("expired");
  });
});

describe("sessionRecovery store semantics", () => {
  it("suppresses the expired phase when there is no redirect target (auth surface)", () => {
    publishExpired(null);
    expect(phase()).toBe("idle");
  });

  it("keeps the expired phase when a redirect target exists", () => {
    publishExpired("/auth/login?redirect=%2Fportal");
    const state = sessionRecoveryStore.getState();
    expect(state.phase).toBe("expired");
    expect(state.redirectTo).toBe("/auth/login?redirect=%2Fportal");
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
    expect(accessDenied).toHaveBeenCalled();
    expect(refreshCalls()).toHaveLength(0);
    expect(phase()).toBe("idle");
  });

  it("500 → plain HttpError, no refresh attempt", async () => {
    stubFetch({ original: [() => res(500, { error: { code: "500", message: "boom" } })], refresh: [] });

    await expect(client.get("/things")).rejects.toBeInstanceOf(HttpError);
    expect(refreshCalls()).toHaveLength(0);
    expect(accessDenied).not.toHaveBeenCalled();
    expect(phase()).toBe("idle");
  });
});
