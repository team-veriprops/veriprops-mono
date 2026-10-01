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
  tiers: [{ tier: VerificationTier.BASIC, priceNgnMinor: 5_000_000, lineItems: [] }],
  upgradeDeltas: [{ fromTier: VerificationTier.BASIC, toTier: VerificationTier.PREMIUM, deltaMinor: 25_000_000 }],
};
const mutateAsync = vi.fn();

vi.mock("./libs/usePricingQueries", () => ({
  usePricingQuery: () => ({ data: view, isLoading: false, isError: false }),
  useSetTierPriceMutation: () => ({ mutateAsync, isPending: false }),
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

describe("AdminPricing", () => {
  /**
   * A price the backend refuses — one that would leave the tier's agent commissions below the
   * minimum margin (§20.1 / D97) — must say so. The refusal is shown through getErrorMessage,
   * so a 4xx reads as the backend's words and a 5xx never leaks server text.
   */
  it("shows a refused price save instead of failing silently", async () => {
    mutateAsync.mockRejectedValueOnce(new Error("refused"));
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
    act(() => root!.render(<AdminPricing />));

    await act(async () => {
      host!.querySelector<HTMLButtonElement>('[data-testid="admin-pricing-save-basic"]')!.click();
    });

    expect(toast.error).toHaveBeenCalledWith("safe: Could not update the price.");
    expect(toast.success).not.toHaveBeenCalled();
  });

  it("humanizes the tiers in the upgrade deltas", () => {
    const html = renderToStaticMarkup(<AdminPricing />);
    expect(html).toContain("Basic → Premium");
    expect(html).not.toContain("BASIC → PREMIUM");
  });
});
