import { describe, it, expect } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import { Accordion, AccordionItem, AccordionTrigger } from "./accordion";

const render = (indicator?: "chevron" | "plus-minus") =>
  renderToStaticMarkup(
    <Accordion type="single">
      <AccordionItem value="a">
        <AccordionTrigger indicator={indicator}>Question</AccordionTrigger>
      </AccordionItem>
    </Accordion>,
  );

describe("AccordionTrigger indicator", () => {
  it("defaults to the rotating chevron", () => {
    const html = render();
    expect(html).toContain("lucide-chevron-down");
    expect(html).not.toContain("lucide-plus");
  });

  it("renders a plus/minus pair when asked, without the chevron", () => {
    const html = render("plus-minus");
    expect(html).toContain("lucide-plus");
    expect(html).toContain("lucide-minus");
    expect(html).not.toContain("lucide-chevron-down");
  });
});
