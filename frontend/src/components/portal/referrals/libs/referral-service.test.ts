import { describe, it, expect } from "vitest";
import { ReferralService } from "./referral-service";
import { HttpClient } from "@lib/FetchHttpClient";

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

describe("ReferralService contract (mirrors app/domain/referral/controller.py)", () => {
  it("gets the caller's referral summary", async () => {
    const { http, calls } = mockHttp();
    await new ReferralService(http).getMine();
    expect(calls[0]).toMatchObject({ method: "get", url: "/referrals/me" });
  });
});
