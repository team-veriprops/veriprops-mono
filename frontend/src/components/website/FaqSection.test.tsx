import { describe, it, expect, afterEach } from "vitest";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";

import FaqSection from "./FaqSection";
import { faqs } from "./home.data";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const mounted: Array<{ root: Root; host: HTMLElement }> = [];

function mount(): HTMLElement {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  act(() => root.render(<FaqSection />));
  mounted.push({ root, host });
  return host;
}

afterEach(() => {
  for (const { root, host } of mounted.splice(0)) {
    act(() => root.unmount());
    host.remove();
  }
});

const triggers = (host: HTMLElement) =>
  [...host.querySelectorAll<HTMLButtonElement>('[data-slot="accordion-trigger"]')];

describe("FaqSection", () => {
  it("lists every FAQ question as a toggle button", () => {
    const host = mount();
    expect(triggers(host).map((t) => t.textContent)).toEqual(faqs.map((f) => f.question));
  });

  it("opens the first question by default, so its answer is readable without a click", () => {
    const host = mount();
    const [first, ...rest] = triggers(host);
    expect(first.getAttribute("aria-expanded")).toBe("true");
    expect(host.textContent).toContain(faqs[0].answer);
    for (const t of rest) expect(t.getAttribute("aria-expanded")).toBe("false");
  });

  it("keeps one answer open at a time", () => {
    const host = mount();
    act(() => triggers(host)[1].click());
    const [first, second] = triggers(host);
    expect(first.getAttribute("aria-expanded")).toBe("false");
    expect(second.getAttribute("aria-expanded")).toBe("true");
    expect(host.textContent).toContain(faqs[1].answer);
  });

  it("marks each row with a plus/minus toggle rather than a chevron", () => {
    const host = mount();
    for (const t of triggers(host)) {
      expect(t.querySelector(".lucide-plus")).not.toBeNull();
      expect(t.querySelector(".lucide-minus")).not.toBeNull();
      expect(t.querySelector(".lucide-chevron-down")).toBeNull();
    }
  });
});
