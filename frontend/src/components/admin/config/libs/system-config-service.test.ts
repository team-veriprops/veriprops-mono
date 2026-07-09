import { describe, it, expect } from "vitest";
import { SystemConfigService } from "./system-config-service";
import { HttpClient } from "@lib/FetchHttpClient";
import { ConfigKey } from "@/types/systemConfig";

function mockHttp() {
  const calls: { method: string; url: string; body?: unknown }[] = [];
  const rec = (method: string) => (url: string, body?: unknown) => {
    calls.push({ method, url, body });
    return Promise.resolve({ status: "success", code: "200", data: [] });
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

describe("SystemConfigService contract (mirrors app/domain/system_config)", () => {
  it("lists settings", async () => {
    const { http, calls } = mockHttp();
    await new SystemConfigService(http).list();
    expect(calls[0]).toMatchObject({ method: "get", url: "/admin/config/settings" });
  });

  it("sets a setting by key", async () => {
    const { http, calls } = mockHttp();
    await new SystemConfigService(http).set(ConfigKey.DISPUTE_WINDOW_DAYS, 45);
    expect(calls[0]).toMatchObject({ method: "put", url: "/admin/config/settings/dispute_window_days" });
    expect(calls[0].body).toMatchObject({ value: 45 });
  });
});
