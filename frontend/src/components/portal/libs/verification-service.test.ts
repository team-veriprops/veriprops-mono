import { describe, it, expect } from "vitest";
import { VerificationService } from "./verification-service";
import { HttpClient } from "@lib/FetchHttpClient";
import { TransactionCurrency } from "@/types/models";
import { PaymentMethodKind, PropertyKind, VerificationTier } from "@/types/verification";

function mockHttp() {
  const calls: { method: string; url: string; body?: unknown; config?: unknown }[] = [];
  const rec = (method: string) => (url: string, body?: unknown, config?: unknown) => {
    calls.push({ method, url, body, config });
    return Promise.resolve({ status: "success", code: "200", data: {} });
  };
  const http = {
    get: (url: string, config?: unknown) => rec("get")(url, undefined, config),
    post: rec("post"),
    put: rec("put"),
    patch: rec("patch"),
    delete: rec("delete"),
  } as unknown as HttpClient;
  return { http, calls };
}

describe("VerificationService contract (mirrors /verifications + /payments)", () => {
  it("creates a draft with an Idempotency-Key header (double-tap protection)", async () => {
    const { http, calls } = mockHttp();
    await new VerificationService(http).createDraft("key-123");
    expect(calls[0].url).toBe("/verifications/draft");
    expect(calls[0].config).toMatchObject({ headers: { "Idempotency-Key": "key-123" } });
  });

  it("requests a quote with tier + currency", async () => {
    const { http, calls } = mockHttp();
    await new VerificationService(http).quote(VerificationTier.STANDARD, TransactionCurrency.USD);
    expect(calls[0].url).toBe("/verifications/quote?tier=STANDARD&currency=USD");
  });

  it("submits with property + tier + consent", async () => {
    const { http, calls } = mockHttp();
    await new VerificationService(http).submit("ver-1", {
      property: { propertyType: PropertyKind.LAND, landmark: "junction" },
      tier: VerificationTier.BASIC,
      currency: TransactionCurrency.NGN,
      consent: { consentVersion: "1.0.0" },
    });
    expect(calls[0]).toMatchObject({ method: "post", url: "/verifications/ver-1/submit" });
  });

  it("initiates payment with an Idempotency-Key and confirms via the stub webhook", async () => {
    const { http, calls } = mockHttp();
    const svc = new VerificationService(http);
    await svc.initiatePayment("ver-1", PaymentMethodKind.CARD, "pay-key");
    await svc.stubConfirm("VP-2026-ABC-xyz", true);
    expect(calls[0].url).toBe("/payments/initiate/ver-1");
    expect(calls[0].config).toMatchObject({ headers: { "Idempotency-Key": "pay-key" } });
    expect(calls[1]).toMatchObject({ url: "/payments/stub/confirm", body: { txRef: "VP-2026-ABC-xyz", succeeded: true } });
  });
});
