import { describe, it, expect, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

const { historyQuery } = vi.hoisted(() => ({
  historyQuery: { current: { data: null as unknown, isLoading: false, isError: false } },
}));

vi.mock("./libs/useConsentHistoryQueries", () => ({
  useConsentHistoryQuery: () => historyQuery.current,
  consentHistoryService: { downloadUrl: () => "/api/users/auth/consents/history/download" },
}));

import ConsentHistory from "./ConsentHistory";

function page(total: number, totalPages: number) {
  return {
    items: [{ documentType: "PLATFORM_TERMS", consentVersion: "2.0", acceptedAt: "2026-09-01T00:00:00Z" }],
    meta: { page: 0, pageSize: 20, count: 1, total, totalPages },
  };
}

function render(data: unknown) {
  historyQuery.current = { data, isLoading: false, isError: false };
  return renderToStaticMarkup(<ConsentHistory />);
}

describe("ConsentHistory (R19.4)", () => {
  it("renders each acceptance with its humanized document type and version", () => {
    const html = render(page(1, 1));
    expect(html).toContain("Platform Terms");
    expect(html).toContain("v2.0");
  });

  it("pages by the backend's page count, not one it works out itself", () => {
    // totalPages comes from the server's meta; a client division by a page size it
    // guessed would disagree with the backend the day either side changes its size.
    const html = render(page(41, 3));
    expect(html).toContain("Page 1 of 3");
  });

  it("shows no pager for a single page", () => {
    expect(render(page(1, 1))).not.toContain("Page 1 of");
  });

  it("says so when nothing has been accepted yet", () => {
    expect(render({ items: [], meta: { page: 0, pageSize: 20, count: 0, total: 0, totalPages: 0 } })).toContain(
      "You have not accepted any versioned agreements yet.",
    );
  });
});
