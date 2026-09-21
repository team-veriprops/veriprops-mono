// @vitest-environment node
// Server-only module: `@lib/config/server` throws wherever `window` exists.
import { afterEach, describe, expect, it, vi } from "vitest";

import { VerificationTier } from "@/types/verification";

const BACKEND = "http://backend.test";

async function loadModule() {
  vi.resetModules();
  vi.stubEnv("API_BASE_URL", BACKEND);
  return import("./public-config.server");
}

const CONFIG = {
  phoneVerificationEnabled: true,
  pricingTiers: [{ tier: VerificationTier.STANDARD, priceNgnMinor: 12_000_000 }],
};

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("fetchPublicConfig", () => {
  it("returns the backend's public config", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ data: CONFIG }), { status: 200 })));
    const { fetchPublicConfig } = await loadModule();

    await expect(fetchPublicConfig()).resolves.toEqual(CONFIG);
  });

  it("revalidates on an interval, so an admin's price edit reaches the prerendered page", async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ data: CONFIG }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const { fetchPublicConfig, PUBLIC_CONFIG_REVALIDATE_SECONDS } = await loadModule();

    await fetchPublicConfig();
    expect(fetchMock).toHaveBeenCalledWith(
      `${BACKEND}/api/config/public`,
      expect.objectContaining({ next: { revalidate: PUBLIC_CONFIG_REVALIDATE_SECONDS } }),
    );
  });

  it("returns null when the backend is unreachable, so a page prerendered without it still renders", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => {
      throw new TypeError("fetch failed");
    }));
    const { fetchPublicConfig } = await loadModule();

    await expect(fetchPublicConfig()).resolves.toBeNull();
  });
});
