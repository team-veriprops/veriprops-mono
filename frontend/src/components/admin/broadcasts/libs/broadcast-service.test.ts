import { describe, it, expect } from "vitest";
import { BroadcastService } from "./broadcast-service";
import { HttpClient } from "@lib/FetchHttpClient";
import { BroadcastAudience } from "@/types/broadcast";

function mockHttp() {
  const calls: { method: string; url: string; body?: unknown }[] = [];
  const rec = (method: string) => (url: string, body?: unknown) => {
    calls.push({ method, url, body });
    return Promise.resolve({ status: "success", code: "200", data: {} });
  };
  const http = { get: (u: string) => rec("get")(u), post: rec("post"), put: rec("put"), patch: rec("patch"), delete: rec("delete") } as unknown as HttpClient;
  return { http, calls };
}

describe("BroadcastService contract (mirrors app/domain/broadcast/controller.py)", () => {
  it("lists with paging params", async () => {
    const { http, calls } = mockHttp();
    await new BroadcastService(http).list(1, 10, "SENT");
    expect(calls[0].method).toBe("get");
    expect(calls[0].url).toContain("/admin/broadcasts?");
    expect(calls[0].url).toContain("page=1");
    expect(calls[0].url).toContain("status=SENT");
  });

  it("previews an audience", async () => {
    const { http, calls } = mockHttp();
    await new BroadcastService(http).preview(BroadcastAudience.CUSTOMERS);
    expect(calls[0]).toMatchObject({ method: "get", url: "/admin/broadcasts/preview?audience=CUSTOMERS" });
  });

  it("composes, sends and cancels", async () => {
    const { http, calls } = mockHttp();
    const svc = new BroadcastService(http);
    await svc.compose({ audience: BroadcastAudience.ALL, subject: "S", body: "B" });
    await svc.send("b-1");
    await svc.cancel("b-1");
    expect(calls[0]).toMatchObject({ method: "post", url: "/admin/broadcasts" });
    expect(calls[1]).toMatchObject({ method: "post", url: "/admin/broadcasts/b-1/send" });
    expect(calls[2]).toMatchObject({ method: "post", url: "/admin/broadcasts/b-1/cancel" });
  });
});
