import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { clampSplit, ResizableSplit, splitAt, SPLIT_MIN_PERCENT } from "./ResizableSplit";

describe("splitAt", () => {
  it("gives the left side the share of the width left of the pointer", () => {
    expect(splitAt(300, { left: 100, width: 800 })).toBe(25);
  });

  it("never lets either side be dragged out of sight", () => {
    expect(splitAt(100, { left: 100, width: 800 })).toBe(SPLIT_MIN_PERCENT);
    expect(splitAt(900, { left: 100, width: 800 })).toBe(100 - SPLIT_MIN_PERCENT);
  });

  it("stays centred over a container with no width yet", () => {
    expect(splitAt(0, { left: 0, width: 0 })).toBe(50);
  });
});

describe("clampSplit", () => {
  it("keeps a keyboard move inside the limits", () => {
    expect(clampSplit(-20)).toBe(SPLIT_MIN_PERCENT);
    expect(clampSplit(60)).toBe(60);
  });
});

describe("ResizableSplit", () => {
  it("starts from the centre with an accessible divider", () => {
    const html = renderToStaticMarkup(
      <ResizableSplit left={<p>A</p>} right={<p>B</p>} label="Resize photos" testId="split" />,
    );
    expect(html).toContain('role="separator"');
    expect(html).toContain('aria-label="Resize photos"');
    expect(html).toContain('aria-valuenow="50"');
    expect(html).toContain('tabindex="0"');
    expect(html).toContain("width:50%");
  });
});
