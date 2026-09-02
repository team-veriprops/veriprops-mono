import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { BotMode, EscalationReason } from "@/types/chat";

/**
 * The banner is the only way out of D57's sticky-`HUMAN` mode, so what is being defended
 * here is that the escape hatch is *visible when it is needed and absent when it is not*.
 * A banner that rendered the hand-back button on a bot-mode thread would invite an agent
 * to "fix" a thread that was never broken; one that hid it on a human-mode thread would
 * leave the customer talking to nobody the moment the agent moved on.
 */

const state: {
  session: {
    phoneE164: string;
    mode: BotMode;
    windowOpen?: boolean;
    lastEscalationReason?: EscalationReason | null;
  } | null;
  isLoading: boolean;
} = { session: null, isLoading: false };

vi.mock("./libs/useWhatsAppBotQueries", () => ({
  useBotSessionQuery: () => ({ data: state.session, isLoading: state.isLoading }),
  useHandBackMutation: () => ({ mutate: vi.fn(), isPending: false }),
}));

const { default: WhatsAppBotModeBanner } = await import("./WhatsAppBotModeBanner");

beforeEach(() => {
  state.session = null;
  state.isLoading = false;
});

describe("WhatsAppBotModeBanner", () => {
  it("offers the way back when a human owns the thread", () => {
    state.session = {
      phoneE164: "+2348012345678",
      mode: BotMode.HUMAN,
      lastEscalationReason: EscalationReason.EXPLICIT_REQUEST,
    };

    const html = renderToStaticMarkup(
      <WhatsAppBotModeBanner phoneE164="+2348012345678" />,
    );

    expect(html).toContain("You&#x27;re handling this thread");
    expect(html).toContain("wa-bot-hand-back");
    // The reason matters: "the customer asked for a person" and "the bot broke" call for
    // very different follow-ups.
    expect(html.toLowerCase()).toContain("explicit request");
  });

  it("says the assistant is answering, with no hand-back to press", () => {
    state.session = { phoneE164: "+2348012345678", mode: BotMode.BOT };

    const html = renderToStaticMarkup(
      <WhatsAppBotModeBanner phoneE164="+2348012345678" />,
    );

    expect(html).toContain("The assistant is answering");
    expect(html).not.toContain("wa-bot-hand-back");
  });

  it("warns that replying will silence the bot", () => {
    // The side effect of sending is invisible otherwise — an agent answering one question
    // would take the customer off the bot without ever being told.
    state.session = { phoneE164: "+2348012345678", mode: BotMode.BOT };

    const html = renderToStaticMarkup(
      <WhatsAppBotModeBanner phoneE164="+2348012345678" />,
    );

    expect(html).toContain("step aside as soon as you reply");
  });

  it("warns when Meta's reply window has closed", () => {
    // Outside the 24-hour window a reply is queued behind a `window_reopen` template
    // rather than delivered as written (§7.7). An agent needs that before they write a
    // long answer, not after.
    state.session = { phoneE164: "+2348012345678", mode: BotMode.HUMAN, windowOpen: false };

    const html = renderToStaticMarkup(
      <WhatsAppBotModeBanner phoneE164="+2348012345678" />,
    );

    expect(html).toContain("wa-window-closed");
    expect(html).toContain("Reply window closed");
  });

  it("stays quiet while the window is open, which is the ordinary case", () => {
    state.session = { phoneE164: "+2348012345678", mode: BotMode.HUMAN, windowOpen: true };

    const html = renderToStaticMarkup(
      <WhatsAppBotModeBanner phoneE164="+2348012345678" />,
    );

    expect(html).not.toContain("wa-window-closed");
  });

  it("renders nothing for a web thread, which has no bot behind it", () => {
    expect(renderToStaticMarkup(<WhatsAppBotModeBanner phoneE164={null} />)).toBe("");
  });

  it("renders nothing before the session resolves", () => {
    state.isLoading = true;

    expect(
      renderToStaticMarkup(<WhatsAppBotModeBanner phoneE164="+2348012345678" />),
    ).toBe("");
  });
});
