import { afterEach, describe, expect, it, vi } from "vitest";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { toast } from "sonner";
import { TierPricingView } from "@/types/pricing";
import { VerificationTier } from "@/types/verification";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock("@lib/errors", () => ({ getErrorMessage: (_err: unknown, fallback: string) => `safe: ${fallback}` }));

const view: TierPricingView = {
  tiers: [{
    tier: VerificationTier.BASIC,
    priceNgnMinor: 5_000_000,
    lineItems: [{ id: "li-1", tier: "BASIC", label: "Verification service fee", amountMinor: 5_000_000, sortOrder: 0, dateCreated: "" }],
  }],
  upgradeDeltas: [{ fromTier: VerificationTier.BASIC, toTier: VerificationTier.PREMIUM, deltaMinor: 25_000_000 }],
};
const mutateAsync = vi.fn();

vi.mock("./libs/usePricingQueries", () => ({
  usePricingQuery: () => ({ data: view, isLoading: false, isError: false }),
  useSetTierPricingMutation: () => ({ mutateAsync, isPending: false }),
}));

import AdminPricing from "./AdminPricing";

let root: Root | null = null;
let host: HTMLElement | null = null;

afterEach(() => {
  act(() => root?.unmount());
  host?.remove();
  root = null;
  host = null;
  vi.clearAllMocks();
});

function mount() {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  act(() => root!.render(<AdminPricing />));
}

const el = <T extends HTMLElement>(testId: string) => host!.querySelector<T>(`[data-testid="${testId}"]`)!;

function type(testId: string, value: string) {
  const input = el<HTMLInputElement>(testId);
  act(() => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(input, value);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
}

async function save() {
  await act(async () => el<HTMLButtonElement>("admin-pricing-save-basic").click());
}

describe("AdminPricing", () => {
  /**
   * The price and its breakdown are one save (§18.1): a new price goes out with the items the
   * admin edited beside it, in kobo, so the breakdown customers see never adds up to an old price.
   */
  it("saves the price and its line items together, in kobo", async () => {
    mutateAsync.mockResolvedValueOnce({});
    mount();
    type("admin-pricing-input-basic", "60000");
    type("admin-pricing-item-amount-basic-0", "45000");
    act(() => el<HTMLButtonElement>("admin-pricing-item-add-basic").click());
    type("admin-pricing-item-label-basic-1", "Search fee");
    type("admin-pricing-item-amount-basic-1", "15,000");
    await save();

    expect(mutateAsync).toHaveBeenCalledWith({
      tier: VerificationTier.BASIC,
      priceNgnMinor: 6_000_000,
      lineItems: [
        { label: "Verification service fee", amountMinor: 4_500_000 },
        { label: "Search fee", amountMinor: 1_500_000 },
      ],
    });
    expect(toast.success).toHaveBeenCalled();
  });

  it("shows the items' running total against the price", () => {
    mount();
    type("admin-pricing-input-basic", "60000");
    expect(el("admin-pricing-items-total-basic").textContent).toContain("50,000");
    expect(el("admin-pricing-items-total-basic").className).toContain("text-destructive");
  });

  it("can remove every line item, leaving the tier without a breakdown", async () => {
    mutateAsync.mockResolvedValueOnce({});
    mount();
    act(() => el<HTMLButtonElement>("admin-pricing-item-remove-basic-0").click());
    await save();
    expect(mutateAsync).toHaveBeenCalledWith(expect.objectContaining({ lineItems: [] }));
  });

  it("refuses an item with no label before calling the backend", async () => {
    mount();
    act(() => el<HTMLButtonElement>("admin-pricing-item-add-basic").click());
    type("admin-pricing-item-amount-basic-1", "100");
    await save();
    expect(mutateAsync).not.toHaveBeenCalled();
    expect(toast.error).toHaveBeenCalled();
  });

  /**
   * A save the backend refuses — a price that would leave the tier's agent commissions below the
   * minimum margin (§20.1 / D97), or items that don't add up — must say so, through
   * getErrorMessage, so a 4xx reads as the backend's words and a 5xx never leaks server text.
   */
  it("shows a refused save instead of failing silently", async () => {
    mutateAsync.mockRejectedValueOnce(new Error("refused"));
    mount();
    await save();
    expect(toast.error).toHaveBeenCalledWith("safe: Could not update the price.");
    expect(toast.success).not.toHaveBeenCalled();
  });

  it("humanizes the tiers in the upgrade deltas", () => {
    const html = renderToStaticMarkup(<AdminPricing />);
    expect(html).toContain("Basic → Premium");
    expect(html).not.toContain("BASIC → PREMIUM");
  });
});
