import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { Conversation, ConversationChannel, ConversationType } from "@/types/chat";
import type { AdminConversationsParams } from "./libs/chat-service";

/**
 * The inbox's job is to put every thread an admin works in one place, named well enough to
 * pick the right one, with what the backend pages and counts — never a client-side filter.
 */

const state: { items: Conversation[]; totalPages: number; lastParams: AdminConversationsParams | null } = {
  items: [],
  totalPages: 1,
  lastParams: null,
};

vi.mock("./libs/useChatQueries", () => ({
  useAdminConversationsQuery: (params: AdminConversationsParams) => {
    state.lastParams = params;
    return {
      data: {
        items: state.items,
        meta: { page: 0, pageSize: 20, count: state.items.length, total: state.items.length, totalPages: state.totalPages },
      },
      isLoading: false,
    };
  },
  useConversationSendMutation: () => ({ mutateAsync: vi.fn() }),
}));
vi.mock("./libs/useAssistantQueries", () => ({ useAssistantReadinessQuery: () => ({ data: undefined }) }));
vi.mock("./ChatThread", () => ({ default: () => null }));
vi.mock("./AssistantModeBanner", () => ({ default: () => null }));

const { default: AdminConversationsInboxContainer } = await import("./AdminConversationsInboxContainer");

function thread(over: Partial<Conversation>): Conversation {
  return { id: "c", type: ConversationType.GENERAL_SUPPORT, channel: ConversationChannel.WEB, closed: false, unread: 0, ...over };
}

beforeEach(() => {
  state.items = [];
  state.totalPages = 1;
  state.lastParams = null;
});

describe("AdminConversationsInboxContainer", () => {
  it("lists web support, WhatsApp and case threads together, named for an admin", () => {
    state.items = [
      thread({ id: "web", ownerName: "Ada Obi", ownerEmail: "ada@example.com", unread: 1 }),
      thread({ id: "wa", channel: ConversationChannel.WHATSAPP, externalRef: "+2348012345678" }),
      thread({ id: "case", type: ConversationType.CUSTOMER_ADMIN, verificationId: "ver-1" }),
    ];

    const html = renderToStaticMarkup(<AdminConversationsInboxContainer />);

    expect(html.match(/data-testid="admin-conversation-row"/g)).toHaveLength(3);
    expect(html).toContain("Ada Obi");
    expect(html).toContain("ada@example.com");
    expect(html).toContain("+2348012345678");
    expect(html).toContain("Not linked to an account");
    expect(html).toContain("Case · customer thread");
  });

  it("asks the backend for the first page of everything by default", () => {
    renderToStaticMarkup(<AdminConversationsInboxContainer />);

    expect(state.lastParams).toEqual({ page: 0, pageSize: 20, filter: undefined, query: undefined });
  });

  it("offers every backend facet plus All, with All selected", () => {
    const html = renderToStaticMarkup(<AdminConversationsInboxContainer />);

    for (const facet of ["all", "support", "whatsapp", "cases"]) {
      expect(html).toContain(`admin-conversations-filter-${facet}`);
    }
    expect(html).toMatch(/aria-pressed="true"[^>]*data-testid="admin-conversations-filter-all"/);
  });

  it("pages with the backend's page count", () => {
    state.items = [thread({ id: "web" })];
    state.totalPages = 3;

    const html = renderToStaticMarkup(<AdminConversationsInboxContainer />);

    expect(html).toContain("admin-conversations-pager-next");
    expect(html).toContain("Page 1 of 3");
  });

  it("says so when there is nothing to work", () => {
    expect(renderToStaticMarkup(<AdminConversationsInboxContainer />)).toContain("No conversations yet.");
  });
});
