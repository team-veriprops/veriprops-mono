import { describe, it, expect } from "vitest";
import { ReviewService, TrustWeightService } from "./review-service";
import { HttpClient } from "@lib/FetchHttpClient";
import { AgentRole } from "@/types/agent";
import { VerificationTier } from "@/types/verification";

function mockHttp() {
  const calls: { method: string; url: string; body?: unknown }[] = [];
  const rec = (method: string) => (url: string, body?: unknown) => {
    calls.push({ method, url, body });
    return Promise.resolve({ status: "success", code: "200", data: {} });
  };
  const http = {
    get: rec("get"),
    post: rec("post"),
    put: rec("put"),
    delete: rec("delete"),
    patch: rec("patch"),
  } as unknown as HttpClient;
  return { http, calls };
}

describe("ReviewService contract (mirrors /admin/review backend routes)", () => {
  it("approves / rejects / reopens a role task", async () => {
    const { http, calls } = mockHttp();
    const svc = new ReviewService(http);
    await svc.approveTask("v-1", AgentRole.FIELD, 90);
    await svc.rejectTask("v-1", AgentRole.FIELD, "blurry");
    await svc.reopenTask("v-1", AgentRole.FIELD);
    expect(calls[0]).toMatchObject({ method: "post", url: "/admin/review/v-1/tasks/FIELD/approve", body: { quality: 90 } });
    expect(calls[1]).toMatchObject({ method: "post", url: "/admin/review/v-1/tasks/FIELD/reject", body: { reason: "blurry" } });
    expect(calls[2]).toMatchObject({ method: "post", url: "/admin/review/v-1/tasks/FIELD/reopen" });
  });

  it("releases and fails a verification", async () => {
    const { http, calls } = mockHttp();
    const svc = new ReviewService(http);
    await svc.release("v-1", "all good");
    await svc.fail("v-1", "fraud");
    expect(calls[0]).toMatchObject({ method: "post", url: "/admin/review/v-1/release", body: { reason: "all good" } });
    expect(calls[1]).toMatchObject({ method: "post", url: "/admin/review/v-1/fail", body: { reason: "fraud" } });
  });
});

describe("TrustWeightService contract (mirrors /admin/trust-score-weights)", () => {
  it("lists and sets tier weights", async () => {
    const { http, calls } = mockHttp();
    const svc = new TrustWeightService(http);
    await svc.list();
    await svc.setTierWeights(VerificationTier.STANDARD, {
      [AgentRole.REGISTRY]: 40,
      [AgentRole.FIELD]: 30,
      [AgentRole.SURVEYOR]: 30,
    } as Record<AgentRole, number>);
    expect(calls[0]).toMatchObject({ method: "get", url: "/admin/trust-score-weights" });
    expect(calls[1]).toMatchObject({
      method: "put",
      url: "/admin/trust-score-weights/STANDARD",
      body: { weights: { REGISTRY: 40, FIELD: 30, SURVEYOR: 30 } },
    });
  });
});
