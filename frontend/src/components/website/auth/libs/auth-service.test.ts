import { describe, it, expect, vi } from "vitest";
import { AuthService } from "./auth-service";
import type { HttpClient } from "@lib/FetchHttpClient";

function makeHttp() {
  const calls: { method: string; url: string }[] = [];
  const record = (method: string) => (url: string) => {
    calls.push({ method, url });
    return Promise.resolve({} as never);
  };
  const http = {
    get: vi.fn(record("get")),
    post: vi.fn(record("post")),
    put: vi.fn(record("put")),
    delete: vi.fn(record("delete")),
  } as unknown as HttpClient;
  return { http, calls };
}

describe("AuthService endpoint contracts (S6)", () => {
  it("listSecurityEvents requests the paginated security events endpoint", () => {
    const { http } = makeHttp();
    new AuthService(http).listSecurityEvents(2, 25);
    expect(http.get).toHaveBeenCalledWith(
      "/users/auth/sessions/security/events?page=2&page_size=25",
    );
  });

  it("listSecurityEvents defaults to page 0 / size 20", () => {
    const { http } = makeHttp();
    new AuthService(http).listSecurityEvents();
    expect(http.get).toHaveBeenCalledWith(
      "/users/auth/sessions/security/events?page=0&page_size=20",
    );
  });

  it("getCrossPortalSummary hits the cross-portal summary endpoint", () => {
    const { http } = makeHttp();
    new AuthService(http).getCrossPortalSummary();
    expect(http.get).toHaveBeenCalledWith("/users/auth/cross-portal/summary");
  });

  it("getPublicConfig hits the public config endpoint (not under /users/auth)", () => {
    const { http } = makeHttp();
    new AuthService(http).getPublicConfig();
    expect(http.get).toHaveBeenCalledWith("/config/public");
  });
});
