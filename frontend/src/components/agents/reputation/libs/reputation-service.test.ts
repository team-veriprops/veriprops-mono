import { describe, it, expect } from "vitest";
import { ReputationService } from "./reputation-service";
import { HttpClient } from "@lib/FetchHttpClient";
import { AvailabilityStatus } from "@/types/agentReputation";
import { AgentRole } from "@/types/agent";

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
    delete: (url: string) => rec("delete")(url),
  } as unknown as HttpClient;
  return { http, calls };
}

describe("ReputationService contract (mirrors app/domain/user/agent/reputation/controller.py)", () => {
  it("gets metrics + profile + coverage", async () => {
    const { http, calls } = mockHttp();
    const svc = new ReputationService(http);
    await svc.getMetrics();
    await svc.getProfile();
    await svc.getCoverage();
    expect(calls[0]).toMatchObject({ method: "get", url: "/agents/me/metrics" });
    expect(calls[1]).toMatchObject({ method: "get", url: "/agents/me/profile" });
    expect(calls[2]).toMatchObject({ method: "get", url: "/agents/me/coverage" });
  });

  it("sets availability", async () => {
    const { http, calls } = mockHttp();
    await new ReputationService(http).setAvailability(AvailabilityStatus.AMBER);
    expect(calls[0]).toMatchObject({ method: "put", url: "/agents/me/availability" });
    expect(calls[0].body).toMatchObject({ availability: "AMBER" });
  });

  it("sets coverage", async () => {
    const { http, calls } = mockHttp();
    await new ReputationService(http).setCoverage([{ state: "lagos" }]);
    expect(calls[0]).toMatchObject({ method: "put", url: "/agents/me/coverage" });
  });

  it("fetches canonical locations", async () => {
    const { http, calls } = mockHttp();
    await new ReputationService(http).getNigeriaLocations();
    expect(calls[0]).toMatchObject({ method: "get", url: "/config/nigeria-locations" });
  });

  it("requests admin suggested agents", async () => {
    const { http, calls } = mockHttp();
    await new ReputationService(http).getSuggestedAgents("v-1", AgentRole.FIELD);
    expect(calls[0].url).toContain("/admin/agents/suggested");
    expect(calls[0].url).toContain("verification_id=v-1");
    expect(calls[0].url).toContain("role=FIELD");
  });
});
