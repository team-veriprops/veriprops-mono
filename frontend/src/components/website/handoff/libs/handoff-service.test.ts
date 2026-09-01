import { describe, it, expect, vi } from "vitest";
import { HandoffIntent } from "@/types/handoff";
import { HandoffService } from "./handoff-service";

function client() {
  // Every method on HttpClient, `getBlob` included — a partial mock does not satisfy the
  // interface and fails `tsc --noEmit`, which is a CI gate even though it is not a
  // `pnpm lint` or `pnpm build` one.
  return {
    get: vi.fn(),
    getBlob: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  };
}

describe("HandoffService", () => {
  it("redeems against the intent's own landing route", async () => {
    // The intent is part of the path so the backend can refuse a token presented at the
    // wrong landing — a report link is not a payment authorization.
    const http = client();
    await new HandoffService(http).redeem(HandoffIntent.PAY, "tok123");
    expect(http.post).toHaveBeenCalledWith("/public/wa/handoff/pay/tok123/redeem");
  });

  it("escapes a token so a malformed link cannot alter the path", async () => {
    const http = client();
    await new HandoffService(http).redeem(HandoffIntent.REPORT, "a/b?c=d");
    expect(http.post).toHaveBeenCalledWith("/public/wa/handoff/report/a%2Fb%3Fc%3Dd/redeem");
  });

  it("starts payment without naming a case", async () => {
    // The case comes from the grant cookie; sending one would invite tampering.
    const http = client();
    await new HandoffService(http).initiatePayment();
    expect(http.post).toHaveBeenCalledWith("/public/wa/handoff/pay/initiate");
  });

  it("releases the grant", async () => {
    const http = client();
    await new HandoffService(http).release();
    expect(http.post).toHaveBeenCalledWith("/public/wa/handoff/release");
  });
});
