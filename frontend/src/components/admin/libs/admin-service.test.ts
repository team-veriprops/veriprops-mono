import { describe, it, expect, vi } from "vitest";
import { AdminService } from "./admin-service";
import { AdminSubRole } from "@/types/admin";
import { HttpClient } from "@lib/FetchHttpClient";

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

describe("AdminService contract (mirrors /users/admins backend routes)", () => {
  it("posts an invitation with camelCase body", async () => {
    const { http, calls } = mockHttp();
    await new AdminService(http).inviteAdmin("a@b.com", AdminSubRole.OPERATIONS);
    expect(calls[0]).toMatchObject({
      method: "post",
      url: "/users/admins/invitations",
      body: { email: "a@b.com", subRole: AdminSubRole.OPERATIONS },
    });
  });

  it("previews an invitation by token (unauthenticated GET)", async () => {
    const { http, calls } = mockHttp();
    await new AdminService(http).previewInvitation("tok-123");
    expect(calls[0]).toMatchObject({ method: "get", url: "/users/admins/invitations/preview/tok-123" });
  });

  it("accepts an invitation with the token in the body", async () => {
    const { http, calls } = mockHttp();
    await new AdminService(http).acceptInvitation("tok-123");
    expect(calls[0]).toMatchObject({ method: "post", url: "/users/admins/invitations/accept", body: { token: "tok-123" } });
  });

  it("changes a member sub-role and deactivates via team routes", async () => {
    const { http, calls } = mockHttp();
    const svc = new AdminService(http);
    await svc.changeSubRole("u-1", AdminSubRole.FINANCE);
    await svc.deactivateMember("u-1");
    expect(calls[0]).toMatchObject({ method: "post", url: "/users/admins/team/u-1/sub-role", body: { subRole: AdminSubRole.FINANCE } });
    expect(calls[1]).toMatchObject({ method: "post", url: "/users/admins/team/u-1/deactivate" });
  });

  it("paginates team + invitations with snake_case query params", async () => {
    const { http, calls } = mockHttp();
    const svc = new AdminService(http);
    await svc.listTeam(2, 10);
    await svc.listInvitations(0, 25);
    expect(calls[0].url).toBe("/users/admins/team?page=2&page_size=10");
    expect(calls[1].url).toBe("/users/admins/invitations?page=0&page_size=25");
  });
});
