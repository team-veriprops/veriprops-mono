import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import HeroSection from "./HeroSection";

describe("HeroSection", () => {
  it("serves its property photo from this site, never a third-party image host", () => {
    const html = renderToStaticMarkup(<HeroSection />);

    expect(html).not.toContain("googleusercontent");
    // next/image may URL-encode the local path into its optimizer URL.
    expect(html).toMatch(/assets(\/|%2F)hero-property/);
    expect(html).toContain('alt="Modern luxury property in Lagos Nigeria"');
  });

  it("loads its photo eagerly: it is the desktop LCP element, and lazy-loading would delay it", () => {
    const html = renderToStaticMarkup(<HeroSection />);

    expect(html).not.toContain('loading="lazy"');
  });
});
