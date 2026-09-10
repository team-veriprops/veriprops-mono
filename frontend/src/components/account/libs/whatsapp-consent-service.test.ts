import { describe, expect, it, vi } from "vitest";

import { WhatsAppConsentService } from "./whatsapp-consent-service";
import { WhatsAppConsentSource } from "@/types/whatsappConsent";

function client() {
  return {
    get: vi.fn().mockResolvedValue({ data: null }),
    getBlob: vi.fn(),
    post: vi.fn().mockResolvedValue({ data: null }),
    put: vi.fn().mockResolvedValue({ data: null }),
    patch: vi.fn(),
    delete: vi.fn().mockResolvedValue({ data: null }),
  };
}

describe("WhatsAppConsentService (§26.4.6)", () => {
  it("reads this account's consents", async () => {
    const http = client();
    await new WhatsAppConsentService(http).get();
    expect(http.get).toHaveBeenCalledWith("/channel/whatsapp/consent/me");
  });

  it("sends both controls together — a partial update would be ambiguous", async () => {
    const http = client();
    await new WhatsAppConsentService(http).set(
      { utility: true, marketing: false },
      WhatsAppConsentSource.PAY_SCREEN,
    );
    const [, body] = http.put.mock.calls[0];
    expect(body).toEqual({ utility: true, marketing: false });
  });

  it("carries the capture point so the §26.8 record says where consent was given", async () => {
    const http = client();
    await new WhatsAppConsentService(http).set(
      { utility: true, marketing: true },
      WhatsAppConsentSource.ACCOUNT_SETTINGS,
    );
    expect(http.put.mock.calls[0][0]).toBe(
      "/channel/whatsapp/consent/me?source=ACCOUNT_SETTINGS",
    );
  });

  it("never sends snake_case field names — the wire is camelCase", async () => {
    const http = client();
    await new WhatsAppConsentService(http).set(
      { utility: true, marketing: true },
      WhatsAppConsentSource.PAY_SCREEN,
    );
    // The body only: the query's `PAY_SCREEN` is an enum *value*, which the backend
    // compares against its own enum and which is snake-shaped by definition.
    expect(JSON.stringify(http.put.mock.calls[0][1])).not.toContain("_");
  });
});
