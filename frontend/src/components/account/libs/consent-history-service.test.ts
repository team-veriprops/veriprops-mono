import { describe, it, expect } from "vitest";
import { ConsentHistoryService } from "./consent-history-service";
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

describe("ConsentHistoryService contract (mirrors app/domain/user/auth/consent/controller.py)", () => {
  it("fetches paged consent history", async () => {
    const { http, calls } = mockHttp();
    await new ConsentHistoryService(http).history(0, 20);
    expect(calls[0]).toMatchObject({ method: "get" });
    expect(calls[0].url).toContain("/users/auth/consents/history?");
    expect(calls[0].url).toContain("page=0");
  });

  it("builds the proxied CSV download link", () => {
    const { http } = mockHttp();
    expect(new ConsentHistoryService(http).downloadUrl()).toBe("/api/users/auth/consents/history/download");
  });
});
