import { describe, it, expect } from "vitest";
import { NotificationService } from "./notification-service";
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

describe("NotificationService contract (mirrors /notifications + /notification-preferences)", () => {
  it("lists the feed (paged) and the unread counter", async () => {
    const { http, calls } = mockHttp();
    const svc = new NotificationService(http);
    await svc.list(1, 20);
    await svc.unreadCount();
    expect(calls[0]).toMatchObject({ method: "get", url: "/notifications?page=1&pageSize=20" });
    expect(calls[1]).toMatchObject({ method: "get", url: "/notifications/unread" });
  });

  it("marks one and all read", async () => {
    const { http, calls } = mockHttp();
    const svc = new NotificationService(http);
    await svc.markRead("n-1");
    await svc.markAllRead();
    expect(calls[0]).toMatchObject({ method: "post", url: "/notifications/n-1/read" });
    expect(calls[1]).toMatchObject({ method: "post", url: "/notifications/read-all" });
  });

  it("reads and writes per-event preferences", async () => {
    const { http, calls } = mockHttp();
    const svc = new NotificationService(http);
    await svc.listPreferences();
    await svc.setPreference("STATUS_CHANGED", true, false);
    expect(calls[0]).toMatchObject({ method: "get", url: "/notification-preferences" });
    expect(calls[1]).toMatchObject({
      method: "put",
      url: "/notification-preferences",
      body: { eventType: "STATUS_CHANGED", emailEnabled: true, smsEnabled: false },
    });
  });
});
