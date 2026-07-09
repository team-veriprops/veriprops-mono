import { describe, it, expect } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { CustomerReport } from "@/types/report";
import { ReportView } from "./ReportView";

function report(overrides: Partial<CustomerReport> = {}): CustomerReport {
  return {
    id: "r1",
    verificationId: "v1",
    vid: "VP-1",
    reportVersion: 1,
    superseded: false,
    trustScore: 82,
    trustBand: "Caution",
    trustMeaning: "Some things to check before you proceed.",
    verdict: "Title confirmed; boundary needs a fresh survey.",
    sections: [
      { key: "executive_summary", title: "Executive summary", body: "All clear-ish.", isLegalOpinion: false },
      { key: "legal_opinion", title: "Legal opinion", body: "Counsel says…", isLegalOpinion: true },
    ],
    legalOpinionIncluded: true,
    acknowledged: true,
    ...overrides,
  };
}

describe("ReportView", () => {
  it("renders the verdict, score, band, and the trust-score gauge", () => {
    const html = renderToStaticMarkup(<ReportView report={report()} legalOpinionEnabled />);
    expect(html).toContain("Title confirmed");
    expect(html).toContain("82");
    expect(html).toContain("Caution");
    expect(html).toContain("<svg"); // the bespoke gauge ring
    expect(html).toContain(LEGAL_MARKER);
  });

  it("hides legal-opinion sections when the flag is off", () => {
    const html = renderToStaticMarkup(<ReportView report={report()} legalOpinionEnabled={false} />);
    expect(html).toContain("Executive summary");
    expect(html).not.toContain("Legal opinion");
  });

  it("shows a placeholder score when none is present yet", () => {
    const html = renderToStaticMarkup(
      <ReportView report={report({ trustScore: undefined, trustBand: "" })} legalOpinionEnabled />,
    );
    expect(html).toContain("Pending");
    expect(html).toContain("—");
  });
});

// A stable fragment of the mandated §3.5 legal footer.
const LEGAL_MARKER = "We reduce uncertainty";
