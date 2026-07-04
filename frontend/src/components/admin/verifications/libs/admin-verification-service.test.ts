import { describe, it, expect } from "vitest";
import { AdminVerificationService } from "./admin-verification-service";
import { HttpClient } from "@lib/FetchHttpClient";
import { AgentRole } from "@/types/agent";
import { VerificationStatus, VerificationTier } from "@/types/verification";
import { AdminNoteCategory } from "@/types/adminVerification";

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

describe("AdminVerificationService contract (mirrors /admin/verifications backend routes)", () => {
  it("lists with snake_case query params and only set filters", async () => {
    const { http, calls } = mockHttp();
    await new AdminVerificationService(http).list(
      { status: VerificationStatus.IN_PROGRESS, tier: VerificationTier.PREMIUM, overdueOnly: true },
      1,
      10,
    );
    expect(calls[0].method).toBe("get");
    expect(calls[0].url).toBe(
      "/admin/verifications?status=IN_PROGRESS&tier=PREMIUM&overdue_only=true&page=1&page_size=10",
    );
  });

  it("omits unset filters from the query string", async () => {
    const { http, calls } = mockHttp();
    await new AdminVerificationService(http).list({}, 0, 10);
    expect(calls[0].url).toBe("/admin/verifications?page=0&page_size=10");
  });

  it("assigns an agent to a role with a camelCase body", async () => {
    const { http, calls } = mockHttp();
    await new AdminVerificationService(http).assign("v-1", AgentRole.FIELD, "agent-9");
    expect(calls[0]).toMatchObject({
      method: "post",
      url: "/admin/verifications/v-1/tasks/FIELD/assign",
      body: { agentId: "agent-9" },
    });
  });

  it("pauses, resumes, cancels and delays via lifecycle routes", async () => {
    const { http, calls } = mockHttp();
    const svc = new AdminVerificationService(http);
    await svc.pause("v-1");
    await svc.resume("v-1");
    await svc.cancel("v-1", "duplicate");
    await svc.setDelay("v-1", 2, "holiday");
    expect(calls[0]).toMatchObject({ method: "post", url: "/admin/verifications/v-1/pause" });
    expect(calls[1]).toMatchObject({ method: "post", url: "/admin/verifications/v-1/resume" });
    expect(calls[2]).toMatchObject({ method: "post", url: "/admin/verifications/v-1/cancel", body: { reason: "duplicate" } });
    expect(calls[3]).toMatchObject({
      method: "post",
      url: "/admin/verifications/v-1/delay",
      body: { extraBusinessDays: 2, reason: "holiday" },
    });
  });

  it("adds an internal note with category + pinned", async () => {
    const { http, calls } = mockHttp();
    await new AdminVerificationService(http).addNote("v-1", AdminNoteCategory.RISK, "watch", true);
    expect(calls[0]).toMatchObject({
      method: "post",
      url: "/admin/verifications/v-1/notes",
      body: { category: AdminNoteCategory.RISK, body: "watch", pinned: true },
    });
  });

  it("submits + resolves chargebacks on the chargeback sub-routes", async () => {
    const { http, calls } = mockHttp();
    const svc = new AdminVerificationService(http);
    await svc.submitRebuttal("cb-1");
    await svc.resolveChargeback("cb-1", true);
    expect(calls[0]).toMatchObject({ method: "post", url: "/admin/verifications/chargebacks/cb-1/rebuttal" });
    expect(calls[1]).toMatchObject({ method: "post", url: "/admin/verifications/chargebacks/cb-1/resolve", body: { won: true } });
  });
});
