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
