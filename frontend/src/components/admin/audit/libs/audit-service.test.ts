import { describe, it, expect } from "vitest";
import { AuditService } from "./audit-service";
import { HttpClient } from "@lib/FetchHttpClient";

function mockHttp() {
  const calls: { method: string; url: string }[] = [];
  const rec = (method: string) => (url: string) => {
    calls.push({ method, url });
    return Promise.resolve({ status: "success", code: "200", data: {} });
  };
  const http = { get: rec("get"), post: rec("post"), put: rec("put"), patch: rec("patch"), delete: rec("delete") } as unknown as HttpClient;
  return { http, calls };
}

describe("AuditService contract (mirrors app/domain/audit/controller.py)", () => {
  it("lists admin actions with action_types + paging", async () => {
    const { http, calls } = mockHttp();
    await new AuditService(http).listAdminActions(["DATA_ERASURE_EXECUTED"], 1, 20);
    expect(calls[0].method).toBe("get");
    expect(calls[0].url).toContain("/admin/audit/actions?");
    expect(calls[0].url).toContain("action_types=DATA_ERASURE_EXECUTED");
    expect(calls[0].url).toContain("page=1");
  });

  it("builds the verification audit-pack download link", () => {
    const { http } = mockHttp();
    const url = new AuditService(http).verificationPackUrl("vid-1");
    expect(url).toBe("/api/admin/audit/verifications/vid-1/export");
  });
});
