import { describe, it, expect } from "vitest";
import {
  buildMetadata,
  pageTitle,
  faqJsonLd,
  organizationJsonLd,
  legalDocumentJsonLd,
  SITE,
} from "./seo";

describe("pageTitle", () => {
  it("returns the site default when no title is given", () => {
    expect(pageTitle()).toBe(SITE.defaultTitle);
  });

  it("appends the brand suffix once", () => {
    expect(pageTitle("Privacy Policy")).toBe("Privacy Policy | Veriprops");
    expect(pageTitle("About Veriprops")).toBe("About Veriprops");
  });
});

describe("buildMetadata", () => {
  it("sets canonical, openGraph, and twitter consistently", () => {
    const meta = buildMetadata({ title: "Terms", description: "d", path: "/legal/terms" });
    expect(meta.alternates?.canonical).toBe("/legal/terms");
    expect((meta.openGraph as { url?: string })?.url).toBe("/legal/terms");
    expect((meta.twitter as { card?: string })?.card).toBe("summary_large_image");
    expect(meta.title).toBe("Terms | Veriprops");
  });

  it("indexes by default and honors noindex", () => {
    expect(buildMetadata().robots).toMatchObject({ index: true, follow: true });
    expect(buildMetadata({ noindex: true }).robots).toMatchObject({ index: false, follow: false });
  });
});

describe("structured data builders", () => {
  it("organizationJsonLd is a valid Organization node", () => {
    const node = organizationJsonLd();
    expect(node["@type"]).toBe("Organization");
    expect(node.name).toBe(SITE.name);
  });

  it("faqJsonLd maps every question to a Q&A entry", () => {
    const node = faqJsonLd([{ question: "q1", answer: "a1" }, { question: "q2", answer: "a2" }]);
    expect(node["@type"]).toBe("FAQPage");
    expect(node.mainEntity).toHaveLength(2);
    expect(node.mainEntity[0]).toMatchObject({
      "@type": "Question",
      name: "q1",
      acceptedAnswer: { text: "a1" },
    });
  });

  it("legalDocumentJsonLd carries version + url", () => {
    const node = legalDocumentJsonLd({ title: "Terms", path: "/legal/terms", version: "1.0.0" });
    expect(node["@type"]).toBe("Article");
    expect(node.version).toBe("1.0.0");
    expect(node.url).toContain("/legal/terms");
  });
});
