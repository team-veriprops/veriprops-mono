import { describe, it, expect } from "vitest";
import { ShareService } from "./share-service";
import { HttpClient } from "@lib/FetchHttpClient";
import { ShareType } from "@/types/share";

function mockHttp() {
  const calls: { method: string; url: string; body?: unknown }[] = [];
  const rec = (method: string) => (url: string, body?: unknown) => {
    calls.push({ method, url, body });
    return Promise.resolve({ status: "success", code: "200", data: {} });
  };
  const http = {
    get: (url: string) => rec("get")(url),
    post: rec("post"),
    put: rec("put"),
    patch: rec("patch"),
    delete: rec("delete"),
  } as unknown as HttpClient;
  return { http, calls };
}

describe("ShareService contract (mirrors app/domain/verification/share)", () => {
  it("lists shares for a verification", async () => {
    const { http, calls } = mockHttp();
    await new ShareService(http).listShares("ver-1");
    expect(calls[0]).toMatchObject({ method: "get", url: "/verifications/ver-1/shares" });
  });

  it("creates a share", async () => {
    const { http, calls } = mockHttp();
    await new ShareService(http).createShare("ver-1", { shareType: ShareType.LINK_SUMMARY });
    expect(calls[0]).toMatchObject({ method: "post", url: "/verifications/ver-1/shares" });
    expect(calls[0].body).toMatchObject({ shareType: ShareType.LINK_SUMMARY });
  });

  it("revokes a share", async () => {
    const { http, calls } = mockHttp();
    await new ShareService(http).revokeShare("ver-1", "s-9");
    expect(calls[0]).toMatchObject({ method: "post", url: "/verifications/ver-1/shares/s-9/revoke" });
  });

  it("toggles public visibility", async () => {
    const { http, calls } = mockHttp();
    await new ShareService(http).setPublicVisibility("ver-1", true);
    expect(calls[0]).toMatchObject({ method: "put", url: "/verifications/ver-1/public-visibility" });
    expect(calls[0].body).toMatchObject({ enabled: true });
  });

  it("looks up a public summary by VID", async () => {
    const { http, calls } = mockHttp();
    await new ShareService(http).publicLookup("VP-ABC");
    expect(calls[0]).toMatchObject({ method: "get", url: "/public/verify/VP-ABC" });
  });

  it("resolves a share token", async () => {
    const { http, calls } = mockHttp();
    await new ShareService(http).resolveShared("tok-1");
    expect(calls[0]).toMatchObject({ method: "get", url: "/public/shared/tok-1" });
  });

  it("acknowledges a shared-report disclaimer", async () => {
    const { http, calls } = mockHttp();
    await new ShareService(http).acknowledgeShared("tok-1");
    expect(calls[0]).toMatchObject({ method: "post", url: "/public/shared/tok-1/acknowledge" });
  });
});
