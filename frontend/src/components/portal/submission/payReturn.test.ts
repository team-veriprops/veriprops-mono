import { describe, expect, it } from "vitest";
import { TransactionCurrency } from "@/types/models";
import {
  Payment,
  PaymentCheckoutKind,
  PaymentMethodKind,
  PaymentPurpose,
  PaymentStatus,
} from "@/types/verification";
import { PayReturn, payReturnOutcome } from "./payReturn";

function payment(over: Partial<Payment> = {}): Payment {
  return {
    id: "pay-1",
    verificationId: "ver-1",
    txRef: "VP-2026-ABC123-x1y2",
    method: PaymentMethodKind.CARD,
    purpose: PaymentPurpose.INITIAL,
    status: PaymentStatus.INITIATED,
    amountMinor: 12_000_000,
    currency: TransactionCurrency.NGN,
    checkoutKind: PaymentCheckoutKind.HOSTED,
    dateCreated: "2026-09-27T12:00:00Z",
    ...over,
  };
}

describe("payReturnOutcome — what the pay page does with the backend's reconciled payment", () => {
  it("has nothing to resume when no payment exists yet", () => {
    expect(payReturnOutcome(null)).toBe(PayReturn.NONE);
  });

  it("goes to the confirmation page once the initial charge has settled", () => {
    expect(payReturnOutcome(payment({ status: PaymentStatus.SUCCEEDED }))).toBe(PayReturn.PAID);
  });

  it("goes back to the verification once a re-check or upgrade charge has settled", () => {
    for (const purpose of [PaymentPurpose.RECHECK, PaymentPurpose.UPGRADE]) {
      expect(payReturnOutcome(payment({ purpose, status: PaymentStatus.SUCCEEDED }))).toBe(PayReturn.SECONDARY_PAID);
    }
  });

  it("waits for the gateway while a hosted charge is still open", () => {
    for (const status of [PaymentStatus.INITIATED, PaymentStatus.PROCESSING, PaymentStatus.PENDING_TRANSFER]) {
      expect(payReturnOutcome(payment({ status }))).toBe(PayReturn.CONFIRMING);
    }
  });

  it("offers a fresh attempt after a failed charge", () => {
    expect(payReturnOutcome(payment({ status: PaymentStatus.FAILED }))).toBe(PayReturn.FAILED);
  });

  it("resumes the stub's confirm step for an open stub charge", () => {
    expect(payReturnOutcome(payment({ checkoutKind: PaymentCheckoutKind.STUB }))).toBe(PayReturn.STUB_PENDING);
  });
});
