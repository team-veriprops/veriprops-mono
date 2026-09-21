import { describe, it, expect } from "vitest";
import {
  Conversation,
  ConversationChannel,
  ConversationReadOnlyReason,
  ConversationType,
} from "@/types/chat";
import {
  adminCaseMessagesHref,
  adminConversationSubtitle,
  adminConversationTitle,
  conversationHref,
  readOnlyNotice,
} from "./conversationLinks";

function conversation(over: Partial<Conversation> = {}): Conversation {
  return {
    id: "conv-1",
    type: ConversationType.GENERAL_SUPPORT,
    channel: ConversationChannel.WEB,
    closed: false,
    unread: 0,
    ...over,
  };
}

describe("conversationHref — where a portal thread opens", () => {
  it("opens the web support thread on the support page", () => {
    expect(conversationHref(conversation())).toBe("/portal/support");
  });

  it("opens a verification thread on that case's messages page", () => {
    expect(
      conversationHref(
        conversation({ type: ConversationType.CUSTOMER_ADMIN, verificationId: "ver-9" }),
      ),
    ).toBe("/portal/verifications/ver-9/messages");
  });

  it("opens a WhatsApp thread by its own id, never the support page", () => {
    // It is also GENERAL_SUPPORT, and linking back to /portal/support (or to the list it
    // came from) was how a customer could see the thread and never open it (§26.8).
    expect(
      conversationHref(conversation({ id: "wa-7", channel: ConversationChannel.WHATSAPP })),
    ).toBe("/portal/chat/wa-7");
  });
});

describe("admin inbox labels — naming threads an admin is not a member of", () => {
  it("names a web support thread by the account behind it", () => {
    const c = conversation({ ownerName: "Ada Obi", ownerEmail: "ada@example.com" });
    expect(adminConversationTitle(c)).toBe("Ada Obi");
    expect(adminConversationSubtitle(c)).toBe("ada@example.com");
  });

  it("names an unlinked WhatsApp enquiry by its number", () => {
    const c = conversation({ channel: ConversationChannel.WHATSAPP, externalRef: "+2348012345678" });
    expect(adminConversationTitle(c)).toBe("+2348012345678");
    expect(adminConversationSubtitle(c)).toBe("Not linked to an account");
  });

  it("moves a linked WhatsApp thread's number under its owner", () => {
    const c = conversation({
      channel: ConversationChannel.WHATSAPP,
      externalRef: "+2348012345678",
      ownerName: "Ada Obi",
    });
    expect(adminConversationTitle(c)).toBe("Ada Obi");
    expect(adminConversationSubtitle(c)).toBe("+2348012345678");
  });

  it("labels a case thread by its side and links to the case", () => {
    const c = conversation({ type: ConversationType.ADMIN_AGENT, verificationId: "ver-9", subject: null });
    expect(adminConversationTitle(c)).toBe("Case · agent thread");
    expect(adminConversationSubtitle(c)).toBe("Case · agent thread");
    expect(adminCaseMessagesHref(c)).toBe("/admin/verifications/ver-9/messages");
    expect(adminCaseMessagesHref(conversation())).toBeNull();
  });
});

describe("readOnlyNotice", () => {
  it("explains an unlinked number in words", () => {
    const notice = readOnlyNotice(ConversationReadOnlyReason.NUMBER_UNLINKED);
    expect(notice).toMatch(/WhatsApp number/);
    expect(notice).not.toContain("NUMBER_UNLINKED");
  });
});
