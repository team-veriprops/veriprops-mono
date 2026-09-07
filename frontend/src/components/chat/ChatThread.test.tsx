import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import {
  ChatMessage,
  ChatMessageState,
  InboundKind,
  MessageKind,
  MessageSource,
  SenderKind,
} from "@/types/chat";

/**
 * The two §26 facts a WhatsApp thread carries that a website thread does not, and that are
 * otherwise **invisible in a message list**:
 *
 * * A photo or voice note the customer sent is *not* evidence (§26.1.6). Without the badge
 *   an agent reading the console has no way to know the survey plan in front of them never
 *   entered the verification file.
 * * A reply typed outside Meta's 24-hour window has not been delivered yet (§26.7). It looks
 *   exactly like a sent message until it is labelled.
 *
 * Both fields are backend-derived and only ever set on a WhatsApp thread, so the shared
 * component needs no surface-specific branch — which is what these tests hold in place.
 */

const state: { messages: ChatMessage[] } = { messages: [] };

vi.mock("./libs/useChatQueries", () => ({
  useMessagesQuery: () => ({ data: { items: state.messages }, isLoading: false }),
  useMarkReadMutation: () => ({ mutate: vi.fn(), isPending: false }),
}));

vi.mock("@components/website/auth/libs/useAuthStore", () => ({
  useAuthStore: (select: (s: unknown) => unknown) =>
    select({ session: { user: { id: "admin-1" } } }),
}));

vi.mock("@components/website/auth/libs/useAuthQueries", () => ({
  usePublicConfigQuery: () => ({ data: { chatMessageMaxLength: 2000 } }),
}));

const { default: ChatThread } = await import("./ChatThread");

function message(over: Partial<ChatMessage> = {}): ChatMessage {
  return {
    id: "m1",
    conversationId: "conv-1",
    body: "[sent an image]",
    state: ChatMessageState.DELIVERED,
    messageKind: MessageKind.CHAT,
    source: MessageSource.WHATSAPP,
    sender: { kind: SenderKind.CUSTOMER, firstName: "Ada" },
    dateCreated: "2026-09-02T09:00:00Z",
    ...over,
  };
}

function render() {
  return renderToStaticMarkup(
    <ChatThread conversationId="conv-1" onSend={async () => undefined} />,
  );
}

beforeEach(() => {
  state.messages = [];
});

describe("ChatThread — §26.6.3 media labelling", () => {
  it("marks a customer's photo as unofficial, never evidence", () => {
    state.messages = [message({ mediaKind: InboundKind.IMAGE, unofficialMedia: true })];

    const html = render();

    expect(html).toContain("chat-unofficial-media");
    expect(html).toContain("not evidence");
  });

  it("names the media kind in words rather than as a raw enum", () => {
    state.messages = [message({ mediaKind: InboundKind.AUDIO, unofficialMedia: true })];

    const html = render();

    expect(html).toContain("Audio");
    expect(html).not.toContain("AUDIO");
  });

  it("leaves ordinary text unbadged", () => {
    // The badge means "notice this". Decorating every message would make it mean nothing.
    state.messages = [message({ body: "How much for a Lagos land check?" })];

    const html = render();

    expect(html).not.toContain("chat-unofficial-media");
  });
});

describe("ChatThread — §26.7 queued replies", () => {
  it("says a reply is waiting on the customer, not sent", () => {
    state.messages = [
      message({
        body: "Sorry for the delay — checking now.",
        sender: { kind: SenderKind.ADMIN, firstName: "Tayo" },
        pendingChannelDelivery: true,
      }),
    ];

    const html = render();

    expect(html).toContain("chat-pending-channel-delivery");
    expect(html).toContain("Waiting for the customer to reply");
  });

  it("shows nothing extra once a reply has gone out", () => {
    state.messages = [
      message({
        body: "Sorry for the delay — checking now.",
        sender: { kind: SenderKind.ADMIN, firstName: "Tayo" },
        pendingChannelDelivery: false,
      }),
    ];

    const html = render();

    expect(html).not.toContain("chat-pending-channel-delivery");
  });

  it("shows nothing on a web thread, where the field is never set", () => {
    state.messages = [
      message({
        source: MessageSource.WEB,
        body: "Thanks — we'll take a look.",
        sender: { kind: SenderKind.ADMIN, firstName: "Tayo" },
      }),
    ];

    const html = render();

    expect(html).not.toContain("chat-pending-channel-delivery");
  });
});
