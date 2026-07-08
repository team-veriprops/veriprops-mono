import { describe, it, expect } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { StatusPill, statusTone } from "./StatusPill";

describe("statusTone", () => {
  it("maps known statuses to their semantic tone", () => {
    expect(statusTone("APPROVED")).toBe("positive");
    expect(statusTone("IN_PROGRESS")).toBe("active");
    expect(statusTone("PENDING")).toBe("warning");
    expect(statusTone("REJECTED")).toBe("negative");
  });

  it("falls back to muted for unknown values", () => {
    expect(statusTone("SOMETHING_NEW")).toBe("muted");
  });
});

describe("StatusPill", () => {
  it("humanizes the status label", () => {
    const html = renderToStaticMarkup(<StatusPill status="UNDER_REVIEW" />);
    expect(html).toContain("Under Review");
    expect(html).not.toContain("UNDER_REVIEW");
  });

  it("applies the resolved tone class", () => {
    const html = renderToStaticMarkup(<StatusPill status="OVERDUE" />);
    expect(html).toContain("text-destructive");
  });
});
