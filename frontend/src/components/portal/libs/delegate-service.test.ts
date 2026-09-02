import { describe, expect, it, vi } from "vitest";

import { DelegateService } from "./delegate-service";

function client() {
  return {
    get: vi.fn().mockResolvedValue({ data: null }),
    getBlob: vi.fn(),
    post: vi.fn().mockResolvedValue({ data: null }),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn().mockResolvedValue({ data: null }),
  };
}

describe("DelegateService (§7.4.5)", () => {
  it("scopes every call to one verification", async () => {
    const http = client();
    await new DelegateService(http).list("v-1");
    expect(http.get).toHaveBeenCalledWith("/verifications/v-1/delegates");
  });

  it("sends the nomination as camelCase", async () => {
    const http = client();
    await new DelegateService(http).authorize("v-1", {
      name: "Tunde",
      phoneE164: "+2348012345678",
    });
    expect(http.post).toHaveBeenCalledWith("/verifications/v-1/delegates", {
      name: "Tunde",
      phoneE164: "+2348012345678",
    });
  });

  it("confirms with the code alone — never the number", async () => {
    // Which number is being confirmed comes from the authorization already on the case,
    // so a browser cannot redirect a code to a number nobody nominated.
    const http = client();
    await new DelegateService(http).confirm("v-1", "654123");
    const [url, body] = http.post.mock.calls[0];
    expect(url).toBe("/verifications/v-1/delegates/confirm");
    expect(body).toEqual({ code: "654123" });
  });

  it("never sends a customer id — ownership is proved server-side", async () => {
    const http = client();
    const service = new DelegateService(http);
    await service.authorize("v-1", { name: "Tunde", phoneE164: "+2348012345678" });
    await service.revoke("v-1");
    expect(JSON.stringify(http.post.mock.calls)).not.toContain("customer");
  });

  it("revokes without a body", async () => {
    const http = client();
    await new DelegateService(http).revoke("v-1");
    expect(http.post).toHaveBeenCalledWith("/verifications/v-1/delegates/revoke");
  });
});
