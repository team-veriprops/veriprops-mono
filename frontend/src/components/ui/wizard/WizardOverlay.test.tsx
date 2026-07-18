import { describe, it, expect } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import WizardOverlay from "./WizardOverlay";

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
