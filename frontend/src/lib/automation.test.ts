import { afterEach, describe, expect, it, vi } from "vitest";

import { isAutomationEnvironment, publishAuthSnapshot } from "./automation";

/** Point the allowlist at a value and re-import-free evaluate (the module reads it live). */
function setEnvironment(value: string | undefined) {
  vi.stubEnv("NEXT_PUBLIC_ENVIRONMENT", value ?? "");
}

afterEach(() => {
  vi.unstubAllEnvs();
  delete window.__auth_snapshot__;
});

describe("isAutomationEnvironment", () => {
  it.each(["dev_personal", "development", "test"])("enables automation for %s", (env) => {
    setEnvironment(env);
    expect(isAutomationEnvironment()).toBe(true);
  });

  it.each(["staging", "production", "", undefined])("stays fail-closed for %s", (env) => {
    setEnvironment(env);
    expect(isAutomationEnvironment()).toBe(false);
  });
});

describe("publishAuthSnapshot", () => {
  it("publishes the signed-in slice", () => {
    setEnvironment("test");
    publishAuthSnapshot({ user: { id: "user-1", personas: ["CUSTOMER"] } });

    expect(window.__auth_snapshot__).toEqual({
      isAuthenticated: true,
      userId: "user-1",
      personas: ["CUSTOMER"],
    });
  });

  it("publishes the signed-out state so a logout is observable", () => {
    setEnvironment("test");
    publishAuthSnapshot(null);

    expect(window.__auth_snapshot__).toEqual({
      isAuthenticated: false,
      userId: null,
      personas: [],
    });
  });

  it("never writes the hook outside automation environments", () => {
    setEnvironment("production");
    publishAuthSnapshot({ user: { id: "user-1", personas: ["CUSTOMER"] } });

    expect(window.__auth_snapshot__).toBeUndefined();
  });
});
