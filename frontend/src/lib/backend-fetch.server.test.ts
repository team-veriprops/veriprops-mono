// @vitest-environment node
// Server-only module: `@lib/config/server` throws wherever `window` exists, so this file
// runs under node rather than the suite's default jsdom.
import { afterEach, describe, expect, it, vi } from "vitest";

const BACKEND = "http://backend.test";

async function loadModule() {
  vi.resetModules();
  vi.stubEnv("API_BASE_URL", BACKEND);
  return import("./backend-fetch.server");
}

const envelope = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("fetchBackendData", () => {
  it("unwraps `data` from the backend's success envelope, addressed under /api", async () => {
    const fetchMock = vi.fn(async () => envelope(200, { data: { ok: 1 } }));
    vi.stubGlobal("fetch", fetchMock);
    const { fetchBackendData } = await loadModule();

    await expect(fetchBackendData("/config/public", { cache: "no-store" })).resolves.toEqual({ ok: 1 });
    expect(fetchMock).toHaveBeenCalledWith(
      `${BACKEND}/api/config/public`,
      expect.objectContaining({ cache: "no-store", headers: { Accept: "application/json" } }),
    );
  });

  it("passes the caller's caching mode through untouched", async () => {
    const fetchMock = vi.fn(async () => envelope(200, { data: [] }));
    vi.stubGlobal("fetch", fetchMock);
    const { fetchBackendData } = await loadModule();

    await fetchBackendData("/users/auth/consents/documents", { next: { revalidate: 3600 } });
    expect(fetchMock).toHaveBeenCalledWith(
      `${BACKEND}/api/users/auth/consents/documents`,
      expect.objectContaining({ next: { revalidate: 3600 } }),
    );
  });

  it("returns null for a non-2xx response", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => envelope(404, { error: { code: "404" } })));
    const { fetchBackendData } = await loadModule();

    await expect(fetchBackendData("/public/verify/VP-X", { cache: "no-store" })).resolves.toBeNull();
  });

  it("returns null when the envelope carries no data", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => envelope(200, {})));
    const { fetchBackendData } = await loadModule();

    await expect(fetchBackendData("/config/public", { cache: "no-store" })).resolves.toBeNull();
  });
});
