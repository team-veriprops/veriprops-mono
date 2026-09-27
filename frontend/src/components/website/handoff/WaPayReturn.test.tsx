import { describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { PaymentStatus } from "@/types/verification";

vi.mock("./libs/handoff-service", () => ({
  HandoffService: class {
    reconcilePayment = vi.fn();
  },
}));
vi.mock("@/containers", () => ({ httpClient: {} }));
vi.mock("@components/website/auth/libs/useAuthQueries", () => ({
  usePublicConfigQuery: () => ({ data: { whatsappNumber: "2349167624347" } }),
}));

import WaPayReturn, { ReturnView, returnViewFor } from "./WaPayReturn";

describe("WaPayReturn — the page a WhatsApp handoff's hosted checkout returns to", () => {
  it("opens by confirming, and shows no case details (the customer has no session)", () => {
    const html = renderToStaticMarkup(<WaPayReturn />);
    expect(html).toContain('data-testid="wa-pay-return-checking"');
    expect(html).toContain("Confirming your payment");
    expect(html).not.toContain("VP-");
  });

  it("follows the backend's reconciled payment status", () => {
    expect(returnViewFor(PaymentStatus.SUCCEEDED)).toBe(ReturnView.RECEIVED);
    expect(returnViewFor(PaymentStatus.FAILED)).toBe(ReturnView.FAILED);
    expect(returnViewFor(PaymentStatus.INITIATED)).toBe(ReturnView.CHECKING);
    expect(returnViewFor(null)).toBe(ReturnView.CHECKING);
  });
});
