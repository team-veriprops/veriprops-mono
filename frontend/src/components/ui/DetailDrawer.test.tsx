import { describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import DetailDrawer from "./DetailDrawer";

function renderDrawer(open: boolean) {
  return renderToStaticMarkup(
    <DetailDrawer title="Payout request" reference="PO-0001" open={open} onOpenChange={vi.fn()}>
      <p>Drawer body</p>
    </DetailDrawer>,
  );
}

describe("DetailDrawer", () => {
  it("is announced as a modal dialog named by its title", () => {
    const html = renderDrawer(true);

    expect(html).toContain('role="dialog"');
    expect(html).toContain('aria-modal="true"');
    const labelledBy = html.match(/aria-labelledby="([^"]+)"/)?.[1];
    expect(labelledBy).toBeTruthy();
    expect(html).toMatch(new RegExp(`id="${labelledBy}"[^>]*>Payout request<`));
  });

  it("carries stable test ids for the drawer and its close control", () => {
    const html = renderDrawer(true);

    expect(html).toContain('data-testid="detail-drawer"');
    expect(html).toMatch(/data-testid="detail-drawer-close"[^>]*aria-label="Close"|aria-label="Close"[^>]*data-testid="detail-drawer-close"/);
  });

  it("renders nothing while closed", () => {
    expect(renderDrawer(false)).not.toContain('data-testid="detail-drawer"');
  });
});
