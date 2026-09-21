import { describe, it, expect } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { MessageSource } from "@/types/chat";
import ChannelBadge from "./ChannelBadge";

describe("ChannelBadge", () => {
  it("labels a WhatsApp-sourced item so an agent knows where a reply goes", () => {
    // §26.3.3: one console, two surfaces — the agent must never guess which.
    const html = renderToStaticMarkup(<ChannelBadge source={MessageSource.WHATSAPP} />);
    expect(html).toContain("WhatsApp");
  });

  it("stays silent for the web surface, which is the unremarkable default", () => {
    expect(renderToStaticMarkup(<ChannelBadge source={MessageSource.WEB} />)).toBe("");
    expect(renderToStaticMarkup(<ChannelBadge source={undefined} />)).toBe("");
  });

  it("exposes the label to assistive tech, not only as colour", () => {
    const html = renderToStaticMarkup(<ChannelBadge source={MessageSource.WHATSAPP} />);
    expect(html).toContain("Received on WhatsApp");
  });
});
