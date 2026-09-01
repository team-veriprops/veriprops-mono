import { describe, it, expect, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import { WhatsAppLinkStatus } from "@/types/whatsappLink";

const { linkQuery } = vi.hoisted(() => ({
  linkQuery: { current: { data: null as unknown, isLoading: false, isError: false } },
}));

vi.mock("./libs/useWhatsAppLinkQueries", () => ({
  useWhatsAppLinkQuery: () => linkQuery.current,
  useStartWhatsAppLinkMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useConfirmWhatsAppLinkMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useUnlinkWhatsAppMutation: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

import WhatsAppLinkSettings from "./WhatsAppLinkSettings";

function render(data: unknown, overrides: Partial<typeof linkQuery.current> = {}) {
  linkQuery.current = { data, isLoading: false, isError: false, ...overrides };
  return renderToStaticMarkup(<WhatsAppLinkSettings />);
}

describe("WhatsAppLinkSettings", () => {
  it("offers to link when the account has no number", () => {
    const html = render(null);
    expect(html).toContain('data-testid="wa-link-send"');
    expect(html).not.toContain('data-testid="wa-link-linked"');
  });

  it("shows the linked number once the link is active", () => {
    const html = render({
      phoneE164: "+2348012345678",
      status: WhatsAppLinkStatus.ACTIVE,
      linkedAt: "2026-09-01T00:00:00Z",
    });
    expect(html).toContain('data-testid="wa-link-linked"');
    expect(html).toContain("+2348012345678");
  });

  it("treats a pending number as not linked", () => {
    // A PENDING row carries a number but grants nothing — rendering it as linked would
    // tell the customer the assistant recognises them when it does not.
    const html = render({
      phoneE164: "+2348012345678",
      status: WhatsAppLinkStatus.PENDING,
    });
    expect(html).not.toContain('data-testid="wa-link-linked"');
    expect(html).toContain('data-testid="wa-link-send"');
  });

  it("treats a revoked link as not linked", () => {
    const html = render({ phoneE164: null, status: WhatsAppLinkStatus.REVOKED });
    expect(html).toContain('data-testid="wa-link-send"');
  });

  it("states up front that a number is never told anything until it is linked", () => {
    // The page's whole justification for existing (§7.4.3 — no case data to an
    // unverified number), so the copy is part of the contract, not decoration.
    expect(render(null)).toContain("never told");
  });

  it("surfaces a load failure rather than rendering an empty linking form", () => {
    const html = render(null, { isError: true });
    expect(html).toContain("Could not load your WhatsApp settings");
    expect(html).not.toContain('data-testid="wa-link-send"');
  });
});
