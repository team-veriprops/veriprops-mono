import { describe, it, expect } from "vitest";
import { RevisionService } from "./revision-service";
import { HttpClient } from "@lib/FetchHttpClient";
import { DisputeOutcome, DisputeType } from "@/types/revision";
import { AgentRole } from "@/types/agent";
import { VerificationTier } from "@/types/verification";

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

describe("RevisionService contract (mirrors app/domain/verification/{recheck,upgrade,dispute})", () => {
  it("requests a re-check", async () => {
    const { http, calls } = mockHttp();
    await new RevisionService(http).requestRecheck("v-1", { reason: "wrong survey" });
    expect(calls[0]).toMatchObject({ method: "post", url: "/verifications/v-1/rechecks" });
  });

  it("admin decides a re-check", async () => {
    const { http, calls } = mockHttp();
    await new RevisionService(http).decideRecheck("rc-1", { approve: true, scopeRoles: [AgentRole.SURVEYOR] });
    expect(calls[0]).toMatchObject({ method: "post", url: "/admin/rechecks/rc-1/decide" });
  });

  it("requests a tier upgrade", async () => {
    const { http, calls } = mockHttp();
    await new RevisionService(http).requestUpgrade("v-1", { toTier: VerificationTier.PREMIUM });
    expect(calls[0]).toMatchObject({ method: "post", url: "/verifications/v-1/upgrades" });
  });

  it("opens a dispute", async () => {
    const { http, calls } = mockHttp();
    await new RevisionService(http).openDispute("v-1", {
      disputeType: DisputeType.INACCURATE_FINDING, description: "x".repeat(100),
    });
    expect(calls[0]).toMatchObject({ method: "post", url: "/verifications/v-1/disputes" });
  });

  it("submits an agent defence", async () => {
    const { http, calls } = mockHttp();
    await new RevisionService(http).submitDefence("d-1", "my account");
    expect(calls[0]).toMatchObject({ method: "post", url: "/agents/disputes/d-1/defence" });
    expect(calls[0].body).toMatchObject({ text: "my account" });
  });

  it("resolves a dispute", async () => {
    const { http, calls } = mockHttp();
    await new RevisionService(http).resolveDispute("d-1", { outcome: DisputeOutcome.REJECTED, note: "n" });
    expect(calls[0]).toMatchObject({ method: "post", url: "/admin/disputes/d-1/resolve" });
  });

  it("lists admin queues", async () => {
    const { http, calls } = mockHttp();
    const svc = new RevisionService(http);
    await svc.listPendingRechecks(0, 10);
    await svc.listOpenDisputes(1, 5);
    expect(calls[0].url).toContain("/admin/rechecks");
    expect(calls[1].url).toContain("/admin/disputes");
  });
});
