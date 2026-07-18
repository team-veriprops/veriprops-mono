import { describe, it, expect } from "vitest";
import { AdminUsersService } from "./admin-users-service";
import { AccountStatus, TrustStatus, UserPersona, UserType } from "@components/website/auth/models";
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

describe("AdminUsersService contract (mirrors /users/admins/users backend routes)", () => {
  it("paginates the directory with snake_case query params", async () => {
    const { http, calls } = mockHttp();
    await new AdminUsersService(http).listUsers({ page: 2, pageSize: 25 });
    expect(calls[0].url).toBe("/users/admins/users?page=2&page_size=25");
  });

  it("forwards search + every filter as snake_case query params", async () => {
    const { http, calls } = mockHttp();
    await new AdminUsersService(http).listUsers({
      page: 0,
      pageSize: 10,
      query: "ada",
      persona: UserPersona.CUSTOMER,
      userType: UserType.USER,
      trustStatus: TrustStatus.TRUSTED,
      accountStatus: AccountStatus.SUSPENDED,
    });
    expect(calls[0].url).toBe(
      `/users/admins/users?page=0&page_size=10&query=ada&persona=${UserPersona.CUSTOMER}` +
        `&user_type=${UserType.USER}&trust_status=${TrustStatus.TRUSTED}` +
        `&account_status=${AccountStatus.SUSPENDED}`,
    );
  });

  it("fetches a user detail by id", async () => {
    const { http, calls } = mockHttp();
    await new AdminUsersService(http).getUserDetail("u-1");
    expect(calls[0]).toMatchObject({ method: "get", url: "/users/admins/users/u-1" });
  });

  it("suspends with a required reason in a camelCase body", async () => {
    const { http, calls } = mockHttp();
    await new AdminUsersService(http).suspendUser("u-1", "Fraud pattern");
    expect(calls[0]).toMatchObject({
      method: "post",
      url: "/users/admins/users/u-1/suspend",
      body: { reason: "Fraud pattern" },
    });
  });

  it("reactivates and forces a password reset via action routes", async () => {
    const { http, calls } = mockHttp();
    const svc = new AdminUsersService(http);
    await svc.reactivateUser("u-1");
    await svc.forcePasswordReset("u-1");
    expect(calls[0]).toMatchObject({ method: "post", url: "/users/admins/users/u-1/reactivate" });
    expect(calls[1]).toMatchObject({ method: "post", url: "/users/admins/users/u-1/password-reset" });
  });

  it("sets trust status with a camelCase body", async () => {
    const { http, calls } = mockHttp();
    await new AdminUsersService(http).setTrustStatus("u-1", TrustStatus.UNTRUSTED);
    expect(calls[0]).toMatchObject({
      method: "post",
      url: "/users/admins/users/u-1/trust-status",
      body: { trustStatus: TrustStatus.UNTRUSTED },
    });
  });
});
