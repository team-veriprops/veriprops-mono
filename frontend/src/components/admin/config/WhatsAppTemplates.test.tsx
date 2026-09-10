import { describe, it, expect, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import { WhatsAppTemplate, WhatsAppTemplateStatus } from "@/types/whatsappTemplate";

const { query, syncSpy } = vi.hoisted(() => ({
  query: { current: { data: [] as unknown, isLoading: false, isError: false } },
  syncSpy: vi.fn(),
}));

vi.mock("./libs/useWhatsAppTemplateQueries", () => ({
  useWhatsAppTemplatesQuery: () => query.current,
  useSyncWhatsAppTemplatesMutation: () => ({ mutateAsync: syncSpy, isPending: false }),
}));

import WhatsAppTemplates from "./WhatsAppTemplates";

function template(over: Partial<WhatsAppTemplate> = {}): WhatsAppTemplate {
  return {
    name: "otp_auth",
    category: "AUTHENTICATION",
    language: "en",
    status: WhatsAppTemplateStatus.NOT_FOUND,
    parameters: ["OTP", "VALIDITY"],
    ...over,
  };
}

function render(templates: WhatsAppTemplate[], overrides = {}) {
  query.current = { data: templates, isLoading: false, isError: false, ...overrides };
  return renderToStaticMarkup(<WhatsAppTemplates />);
}

describe("WhatsAppTemplates", () => {
  it("lists a declared template with its category and ordered parameters", () => {
    const html = render([template()]);
    expect(html).toContain("otp_auth");
    expect(html).toContain("AUTHENTICATION");
    // The order is the contract with Meta's positional body parameters.
    expect(html).toContain("OTP → VALIDITY");
  });

  it("says a NOT_FOUND template still has to be submitted", () => {
    // The state the §26.11 launch gate is really asking about, so it must not read as a
    // generic failure the reader can ignore.
    const html = render([template()]);
    expect(html).toContain("not on the business account yet");
  });

  it("surfaces Meta's rejection reason, which is the only actionable part", () => {
    const html = render([
      template({ status: WhatsAppTemplateStatus.REJECTED, rejectionReason: "INVALID_FORMAT" }),
    ]);
    expect(html).toContain("INVALID_FORMAT");
  });

  it("does not nag about submission once a template is approved", () => {
    const html = render([template({ status: WhatsAppTemplateStatus.APPROVED })]);
    expect(html).not.toContain("not on the business account yet");
    expect(html).toContain("Approved");
  });

  it("offers a sync action and nothing editable", () => {
    // Definitions are code-owned and status is Meta's — an input here would let the page
    // claim something the app does not do.
    const html = render([template()]);
    expect(html).toContain('data-testid="wa-templates-sync"');
    expect(html).not.toContain("<input");
  });

  it("surfaces a load failure rather than an empty registry", () => {
    const html = render([], { isError: true });
    expect(html).not.toContain('data-testid="wa-template-otp_auth"');
  });
});
