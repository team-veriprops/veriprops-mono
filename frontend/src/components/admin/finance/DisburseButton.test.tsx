import { describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { DisbursementQueue } from "@/types/payout";

const queue: { data: DisbursementQueue | null } = { data: null };

vi.mock("./libs/useFinanceQueries", () => ({
  useDisbursementQueueQuery: () => queue,
  useDisburseMutation: () => ({ mutate: vi.fn(), isPending: false }),
}));

import DisburseButton, { disburseLabel, disbursementSummary } from "./DisburseButton";

describe("DisburseButton", () => {
  it("names how many payouts wait and what they will draw", () => {
    queue.data = { count: 3, totalMinor: 15_000_000, inFlight: 0 };
    const html = renderToStaticMarkup(<DisburseButton />);
    expect(html).toContain("Disburse 3 approved");
    expect(html).toContain("150,000");
    expect(html).not.toContain('disabled=""');
  });

  it("is disabled when nothing is approved and nothing is with the bank", () => {
    queue.data = { count: 0, totalMinor: 0, inFlight: 0 };
    const html = renderToStaticMarkup(<DisburseButton />);
    expect(html).toContain("Nothing to disburse");
    expect(html).toContain('disabled=""');
  });

  it("still runs to settle transfers whose webhook never came", () => {
    queue.data = { count: 0, totalMinor: 0, inFlight: 2 };
    const html = renderToStaticMarkup(<DisburseButton />);
    expect(html).toContain("Check 2 transfers with the bank");
    expect(html).not.toContain('disabled=""');
    expect(disburseLabel(0, 0, 1)).toBe("Check 1 transfer with the bank");
  });
});

describe("disbursementSummary", () => {
  it("reports each outcome, and when another press is needed", () => {
    expect(disbursementSummary({ paid: 2, failed: 0, inFlight: 0, remaining: 0 })).toBe("2 paid.");
    expect(disbursementSummary({ paid: 1, failed: 1, inFlight: 1, remaining: 4 }))
      .toBe("1 paid, 1 failed, 1 still with the bank. 4 more waiting — disburse again to send them.");
  });
});
