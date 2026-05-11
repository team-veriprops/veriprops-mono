import { describe, it, expect, vi, beforeEach } from "vitest";
import { AdminService } from "./admin-service";
import type { HttpClient } from "@lib/FetchHttpClient";
import type { AdminInvitation, AcceptInviteResult, InviteAdminResult } from "./admin-service";

const mockInvitation: AdminInvitation = {
  id: "inv-001",
  email: "ops@example.com",
  subRole: "OPERATIONS",
  status: "PENDING",
  inviterAdminId: "admin-001",
  expiresAt: "2099-12-31T00:00:00Z",
  acceptedAt: null,
  createdAt: "2026-05-07T00:00:00Z",
};

function makeHttp(): { mock: Record<string, ReturnType<typeof vi.fn>>; client: HttpClient } {
  const mock = {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  };
  return { mock, client: mock as unknown as HttpClient };
}

describe("AdminService — invitations", () => {
  let http: ReturnType<typeof makeHttp>;
  let service: AdminService;

  beforeEach(() => {
    http = makeHttp();
    service = new AdminService(http.client);
  });

  it("inviteAdmin posts to /users/admin-invitations with email and subRole", async () => {
    const result: InviteAdminResult = { invitation: mockInvitation, rawToken: "tok_abc" };
    http.mock.post.mockResolvedValue({ data: result });

    const res = await service.inviteAdmin({ email: "ops@example.com", subRole: "OPERATIONS" });

    expect(http.mock.post).toHaveBeenCalledWith("/users/admin-invitations", {
      email: "ops@example.com",
      subRole: "OPERATIONS",
    });
    expect(res.data?.rawToken).toBe("tok_abc");
    expect(res.data?.invitation.email).toBe("ops@example.com");
  });

  it("listInvitations calls GET /users/admin-invitations without status filter", async () => {
    http.mock.get.mockResolvedValue({ items: [mockInvitation], meta: {} });

    await service.listInvitations();

    expect(http.mock.get).toHaveBeenCalledWith("/users/admin-invitations");
  });

  it("listInvitations appends status query param when provided", async () => {
    http.mock.get.mockResolvedValue({ items: [], meta: {} });

    await service.listInvitations("PENDING");

    expect(http.mock.get).toHaveBeenCalledWith("/users/admin-invitations?status=PENDING");
  });

  it("revokeInvitation posts to /users/admin-invitations/{id}/revoke", async () => {
    http.mock.post.mockResolvedValue({ data: true });

    await service.revokeInvitation("inv-001");

    expect(http.mock.post).toHaveBeenCalledWith("/users/admin-invitations/inv-001/revoke", {});
  });

  it("acceptInvitation posts to /users/admin-invitations/accept with token", async () => {
    const result: AcceptInviteResult = {
      branch: "ACCEPTED",
      email: "ops@example.com",
      subRole: "OPERATIONS",
    };
    http.mock.post.mockResolvedValue({ data: result });

    const res = await service.acceptInvitation("raw-token-abc");

    expect(http.mock.post).toHaveBeenCalledWith("/users/admin-invitations/accept", {
      token: "raw-token-abc",
    });
    expect(res.data?.branch).toBe("ACCEPTED");
  });

  it("acceptInvitation returns SIGNUP_REQUIRED branch correctly", async () => {
    const result: AcceptInviteResult = {
      branch: "SIGNUP_REQUIRED",
      email: "newuser@example.com",
      subRole: "FINANCE",
    };
    http.mock.post.mockResolvedValue({ data: result });

    const res = await service.acceptInvitation("invite-tok");

    expect(res.data?.branch).toBe("SIGNUP_REQUIRED");
    expect(res.data?.email).toBe("newuser@example.com");
    expect(res.data?.subRole).toBe("FINANCE");
  });

  it("acceptInvitation returns LOGIN_REQUIRED branch correctly", async () => {
    const result: AcceptInviteResult = {
      branch: "LOGIN_REQUIRED",
      email: "existing@example.com",
      subRole: null,
    };
    http.mock.post.mockResolvedValue({ data: result });

    const res = await service.acceptInvitation("invite-tok");

    expect(res.data?.branch).toBe("LOGIN_REQUIRED");
  });

  it("acceptInvitation returns ALREADY_ADMIN branch correctly", async () => {
    const result: AcceptInviteResult = {
      branch: "ALREADY_ADMIN",
      email: "admin@example.com",
      subRole: null,
    };
    http.mock.post.mockResolvedValue({ data: result });

    const res = await service.acceptInvitation("invite-tok");

    expect(res.data?.branch).toBe("ALREADY_ADMIN");
  });
});

// ── Verification queue ────────────────────────────────────────────────────────

describe("AdminService — verifications", () => {
  let http: ReturnType<typeof makeHttp>;
  let service: AdminService;

  beforeEach(() => {
    http = makeHttp();
    service = new AdminService(http.client);
  });

  it("listVerifications calls GET /admin/verifications with no params when none provided", async () => {
    http.mock.get.mockResolvedValue({ items: [], meta: {} });

    await service.listVerifications();

    expect(http.mock.get).toHaveBeenCalledWith("/admin/verifications");
  });

  it("listVerifications appends status and tier filters", async () => {
    http.mock.get.mockResolvedValue({ items: [], meta: {} });

    await service.listVerifications({ status: "PAID", tier: "STANDARD", page: 2 });

    const url = http.mock.get.mock.calls[0][0] as string;
    expect(url).toContain("status=PAID");
    expect(url).toContain("tier=STANDARD");
    expect(url).toContain("page=2");
  });

  it("getVerification calls GET /admin/verifications/{vid}", async () => {
    http.mock.get.mockResolvedValue({ data: {} });

    await service.getVerification("VP-2026-ABC123");

    expect(http.mock.get).toHaveBeenCalledWith("/admin/verifications/VP-2026-ABC123");
  });

  it("pauseVerification posts to /admin/verifications/{vid}/pause", async () => {
    http.mock.post.mockResolvedValue({ data: {} });

    await service.pauseVerification("VP-2026-001");

    expect(http.mock.post).toHaveBeenCalledWith("/admin/verifications/VP-2026-001/pause", {});
  });

  it("resumeVerification posts to /admin/verifications/{vid}/resume", async () => {
    http.mock.post.mockResolvedValue({ data: {} });

    await service.resumeVerification("VP-2026-001");

    expect(http.mock.post).toHaveBeenCalledWith("/admin/verifications/VP-2026-001/resume", {});
  });

  it("cancelVerification posts to /admin/verifications/{vid}/cancel", async () => {
    http.mock.post.mockResolvedValue({ data: {} });

    await service.cancelVerification("VP-2026-001");

    expect(http.mock.post).toHaveBeenCalledWith("/admin/verifications/VP-2026-001/cancel", {});
  });

  it("failVerification posts reason to /admin/verifications/{vid}/fail", async () => {
    http.mock.post.mockResolvedValue({ data: {} });

    await service.failVerification("VP-2026-001", "Invalid documents");

    expect(http.mock.post).toHaveBeenCalledWith("/admin/verifications/VP-2026-001/fail", {
      reason: "Invalid documents",
    });
  });

  it("addNote posts content/tags/pinned to /admin/verifications/{vid}/notes", async () => {
    http.mock.post.mockResolvedValue({ data: {} });

    await service.addNote("VP-2026-001", { content: "Flagged for review", tags: ["urgent"], pinned: true });

    expect(http.mock.post).toHaveBeenCalledWith("/admin/verifications/VP-2026-001/notes", {
      content: "Flagged for review",
      tags: ["urgent"],
      pinned: true,
    });
  });

  it("releaseToPool posts to /admin/verifications/{vid}/release-to-pool", async () => {
    http.mock.post.mockResolvedValue({ data: {} });

    await service.releaseToPool("VP-2026-001");

    expect(http.mock.post).toHaveBeenCalledWith("/admin/verifications/VP-2026-001/release-to-pool", {});
  });
});

// ── Task assignment ───────────────────────────────────────────────────────────

describe("AdminService — tasks", () => {
  let http: ReturnType<typeof makeHttp>;
  let service: AdminService;

  beforeEach(() => {
    http = makeHttp();
    service = new AdminService(http.client);
  });

  it("listTasksForVerification calls GET /admin/verifications/{vid}/tasks", async () => {
    http.mock.get.mockResolvedValue({ data: [] });

    await service.listTasksForVerification("VP-2026-001");

    expect(http.mock.get).toHaveBeenCalledWith("/admin/verifications/VP-2026-001/tasks");
  });

  it("assignTask posts agentId to /admin/verifications/{vid}/tasks/{role}/assign", async () => {
    http.mock.post.mockResolvedValue({ data: {} });

    await service.assignTask("VP-2026-001", "FIELD", "agent-abc");

    expect(http.mock.post).toHaveBeenCalledWith(
      "/admin/verifications/VP-2026-001/tasks/FIELD/assign",
      { agentId: "agent-abc" },
    );
  });

  it("reassignTask posts agentId and note to /admin/tasks/{taskId}/reassign", async () => {
    http.mock.post.mockResolvedValue({ data: {} });

    await service.reassignTask("task-001", "agent-xyz", "Unavailable agent replaced");

    expect(http.mock.post).toHaveBeenCalledWith("/admin/tasks/task-001/reassign", {
      agentId: "agent-xyz",
      note: "Unavailable agent replaced",
    });
  });

  it("listAvailableAgents calls GET /admin/agents/available with role filter", async () => {
    http.mock.get.mockResolvedValue({ data: [] });

    await service.listAvailableAgents({ role: "FIELD", state: "LAGOS" });

    const url = http.mock.get.mock.calls[0][0] as string;
    expect(url).toContain("role=FIELD");
    expect(url).toContain("state=LAGOS");
  });
});

// ── System config ─────────────────────────────────────────────────────────────

describe("AdminService — config", () => {
  let http: ReturnType<typeof makeHttp>;
  let service: AdminService;

  beforeEach(() => {
    http = makeHttp();
    service = new AdminService(http.client);
  });

  it("listConfig calls GET /admin/config", async () => {
    http.mock.get.mockResolvedValue({ data: [] });

    await service.listConfig();

    expect(http.mock.get).toHaveBeenCalledWith("/admin/config");
  });

  it("setConfig puts value to /admin/config/{key}", async () => {
    http.mock.put.mockResolvedValue({ data: {} });

    await service.setConfig("no_show_timeout_hours", "8");

    expect(http.mock.put).toHaveBeenCalledWith("/admin/config/no_show_timeout_hours", {
      value: "8",
    });
  });
});
