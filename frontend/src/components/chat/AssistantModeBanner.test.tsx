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
    conversationId: string;
    enabled: boolean;
    mode: BotMode;
    windowOpen?: boolean | null;
    lastEscalationReason?: EscalationReason | null;
  } | null;
  isLoading: boolean;
} = { session: null, isLoading: false };

vi.mock("./libs/useAssistantQueries", () => ({
  useAssistantSessionQuery: () => ({ data: state.session, isLoading: state.isLoading }),
  useHandBackMutation: () => ({ mutate: vi.fn(), isPending: false }),
}));

const { default: AssistantModeBanner } = await import("./AssistantModeBanner");

beforeEach(() => {
  state.session = null;
  state.isLoading = false;
});

describe("AssistantModeBanner", () => {
  it("offers the way back when a human owns the thread", () => {
    state.session = {
      conversationId: "conv-1",
      enabled: true,
      mode: BotMode.HUMAN,
      lastEscalationReason: EscalationReason.EXPLICIT_REQUEST,
    };

    const html = renderToStaticMarkup(<AssistantModeBanner conversationId="conv-1" />);

    expect(html).toContain("You&#x27;re handling this thread");
    expect(html).toContain("wa-bot-hand-back");
    // The reason matters: "the customer asked for a person" and "the bot broke" call for
    // very different follow-ups.
    expect(html.toLowerCase()).toContain("explicit request");
  });

  it("says the assistant is answering, with no hand-back to press", () => {
    state.session = { conversationId: "conv-1", enabled: true, mode: BotMode.BOT };

    const html = renderToStaticMarkup(<AssistantModeBanner conversationId="conv-1" />);

    expect(html).toContain("The assistant is answering");
    expect(html).not.toContain("wa-bot-hand-back");
  });

  it("warns that replying will silence the assistant", () => {
    // The side effect of sending is invisible otherwise — an agent answering one question
    // would take the customer off the assistant without ever being told.
    state.session = { conversationId: "conv-1", enabled: true, mode: BotMode.BOT };

    const html = renderToStaticMarkup(<AssistantModeBanner conversationId="conv-1" />);

    expect(html).toContain("step aside as soon as you reply");
  });

  it("warns when Meta's reply window has closed, on WhatsApp", () => {
    // Outside the 24-hour window a reply is queued behind a `window_reopen` template
    // rather than delivered as written (§26.7). An agent needs that before they write a
    // long answer, not after.
    state.session = { conversationId: "conv-1", enabled: true, mode: BotMode.HUMAN, windowOpen: false };

    const html = renderToStaticMarkup(<AssistantModeBanner conversationId="conv-1" />);

    expect(html).toContain("wa-window-closed");
    expect(html).toContain("Reply window closed");
  });

  it("stays quiet while the window is open, which is the ordinary case", () => {
    state.session = { conversationId: "conv-1", enabled: true, mode: BotMode.HUMAN, windowOpen: true };

    const html = renderToStaticMarkup(<AssistantModeBanner conversationId="conv-1" />);

    expect(html).not.toContain("wa-window-closed");
  });

  it("has no window chip on a web thread, where windowOpen is null", () => {
    state.session = { conversationId: "conv-1", enabled: true, mode: BotMode.HUMAN, windowOpen: null };

    const html = renderToStaticMarkup(<AssistantModeBanner conversationId="conv-1" />);

    expect(html).not.toContain("wa-window-closed");
  });

  it("renders nothing for a thread the assistant never answers (admin↔agent)", () => {
    state.session = { conversationId: "conv-1", enabled: false, mode: BotMode.BOT };

    expect(renderToStaticMarkup(<AssistantModeBanner conversationId="conv-1" />)).toBe("");
  });

  it("renders nothing with no conversation", () => {
    expect(renderToStaticMarkup(<AssistantModeBanner conversationId={null} />)).toBe("");
  });

  it("renders nothing before the session resolves", () => {
    state.isLoading = true;

    expect(renderToStaticMarkup(<AssistantModeBanner conversationId="conv-1" />)).toBe("");
  });
});
