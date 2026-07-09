import { describe, it, expect } from "vitest";
import { ErasureService } from "./erasure-service";
import { HttpClient } from "@lib/FetchHttpClient";

function mockHttp() {
  const calls: { method: string; url: string; body?: unknown }[] = [];
  const rec = (method: string) => (url: string, body?: unknown) => {
    calls.push({ method, url, body });
    return Promise.resolve({ status: "success", code: "200", data: {} });
  };
  const http = { get: (u: string) => rec("get")(u), post: rec("post"), put: rec("put"), patch: rec("patch"), delete: rec("delete") } as unknown as HttpClient;
  return { http, calls };
}

describe("ErasureService contract (mirrors app/domain/compliance/erasure/controller.py)", () => {
  it("self-service: requests and lists own erasure requests", async () => {
    const { http, calls } = mockHttp();
    const svc = new ErasureService(http);
    await svc.requestMine("please erase");
    await svc.listMine();
    expect(calls[0]).toMatchObject({ method: "post", url: "/users/me/erasure-requests", body: { reason: "please erase" } });
    expect(calls[1]).toMatchObject({ method: "get", url: "/users/me/erasure-requests" });
  });

  it("admin: lists with status + paging params", async () => {
    const { http, calls } = mockHttp();
    await new ErasureService(http).list("PENDING", 2, 10);
    expect(calls[0].method).toBe("get");
    expect(calls[0].url).toContain("/admin/erasure-requests?");
    expect(calls[0].url).toContain("page=2");
    expect(calls[0].url).toContain("status=PENDING");
  });

  it("admin: approves, rejects and executes", async () => {
    const { http, calls } = mockHttp();
    const svc = new ErasureService(http);
    await svc.approve("e-1");
    await svc.reject("e-1", "not verified");
    await svc.execute("e-1");
    expect(calls[0]).toMatchObject({ method: "post", url: "/admin/erasure-requests/e-1/approve" });
    expect(calls[1]).toMatchObject({ method: "post", url: "/admin/erasure-requests/e-1/reject", body: { note: "not verified" } });
    expect(calls[2]).toMatchObject({ method: "post", url: "/admin/erasure-requests/e-1/execute" });
  });
});
