import { describe, it, expect, vi } from "vitest";

import { WhatsAppLinkService } from "./whatsapp-link-service";

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

describe("WhatsAppLinkService", () => {
  it("reads the account's link from the linking controller", async () => {
    const http = client();
    await new WhatsAppLinkService(http).get();
    expect(http.get).toHaveBeenCalledWith("/channel/whatsapp/link/me");
  });

  it("sends the number as camelCase, matching the backend alias generator", async () => {
    const http = client();
    await new WhatsAppLinkService(http).start("+2348012345678");
    expect(http.post).toHaveBeenCalledWith("/channel/whatsapp/link/me/start", {
      phoneE164: "+2348012345678",
    });
  });

  it("confirms with the number the code was sent to, plus the code", async () => {
    const http = client();
    await new WhatsAppLinkService(http).confirm("+2348012345678", "654123");
    expect(http.post).toHaveBeenCalledWith("/channel/whatsapp/link/me/confirm", {
      phoneE164: "+2348012345678",
      code: "654123",
    });
  });

  it("unlinks with a DELETE, carrying no body to be tampered with", async () => {
    const http = client();
    await new WhatsAppLinkService(http).unlink();
    expect(http.delete).toHaveBeenCalledWith("/channel/whatsapp/link/me");
  });

  describe("the WhatsApp→web direction", () => {
    // §26.4.4: the number is named by the bot's signed token. If the browser could send
    // a number here, a signed-in attacker could have a code posted to any number they
    // liked — which is exactly the attack the token shape exists to prevent.
    it("starts with the token alone — never a number", async () => {
      const http = client();
      await new WhatsAppLinkService(http).startFromToken("signed-token");
      expect(http.post).toHaveBeenCalledWith("/channel/whatsapp/link/from-token/start", {
        token: "signed-token",
      });
      expect(JSON.stringify(http.post.mock.calls)).not.toContain("phone");
    });

    it("confirms with the token and the code — never a number", async () => {
      const http = client();
      await new WhatsAppLinkService(http).confirmFromToken("signed-token", "654123");
      expect(http.post).toHaveBeenCalledWith("/channel/whatsapp/link/from-token/confirm", {
        token: "signed-token",
        code: "654123",
      });
      expect(JSON.stringify(http.post.mock.calls)).not.toContain("phone");
    });
  });
});
