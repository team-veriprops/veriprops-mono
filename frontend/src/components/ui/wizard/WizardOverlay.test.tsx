import { describe, it, expect, afterEach } from "vitest";
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { Dialog, DialogContent, DialogTitle } from "@3rdparty/ui/dialog";
import WizardOverlay from "./WizardOverlay";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

function render(closable?: boolean): string {
  return renderToStaticMarkup(
    <WizardOverlay
      steps={["One", "Two"]}
      current={0}
      onClose={() => {}}
      title="Test wizard"
      testIdPrefix="test-wizard"
      closable={closable}
    >
      <div>content</div>
    </WizardOverlay>,
  );
}

describe("WizardOverlay closable", () => {
  it("shows the close control by default", () => {
    const html = render();
    expect(html).toContain("test-wizard-close");
  });

  it("shows the close control when closable=true", () => {
    const html = render(true);
    expect(html).toContain("test-wizard-close");
  });

  it("hides the close control when closable=false (compulsory flow)", () => {
    const html = render(false);
    expect(html).not.toContain("test-wizard-close");
  });
});

/** Reads the Tailwind `z-N` utility off an element's class list. */
function zIndexOf(el: Element | null): number {
  const match = el?.className.match(/(?:^|\s)z-(\d+)(?:\s|$)/);
  if (!match) throw new Error(`no z-N class on ${el?.outerHTML.slice(0, 120)}`);
  return Number(match[1]);
}

describe("WizardOverlay stacking", () => {
  let root: Root | null = null;
  let host: HTMLElement | null = null;

  afterEach(() => {
    act(() => root?.unmount());
    host?.remove();
    root = null;
    host = null;
  });

  // A global modal (updated-terms re-acceptance, session recovery) can open while a wizard is up.
  // Radix disables pointer events outside an open modal, so if the wizard painted above it the
  // user would see the form but be unable to use either surface.
  it("sits below portaled dialogs so a modal opened over a wizard stays visible and usable", () => {
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
    act(() =>
      root!.render(
        <>
          <WizardOverlay
            steps={["One"]}
            current={0}
            onClose={() => {}}
            testIdPrefix="test-wizard"
          >
            <div>content</div>
          </WizardOverlay>
          <Dialog open>
            <DialogContent aria-describedby={undefined}>
              <DialogTitle>Mandatory</DialogTitle>
            </DialogContent>
          </Dialog>
        </>,
      ),
    );

    const wizard = zIndexOf(document.querySelector('[data-testid="test-wizard-overlay"]'));
    expect(wizard).toBeLessThan(zIndexOf(document.querySelector('[data-slot="dialog-overlay"]')));
    expect(wizard).toBeLessThan(zIndexOf(document.querySelector('[data-slot="dialog-content"]')));
  });
});
