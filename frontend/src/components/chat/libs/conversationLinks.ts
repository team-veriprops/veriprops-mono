import { ROUTES } from "@lib/routes";
import {
  Conversation,
  ConversationChannel,
  ConversationReadOnlyReason,
  ConversationType,
} from "@/types/chat";

/**
 * Where a thread in the customer's conversation list opens.
 *
 * A thread with a page of its own opens there (a case's messages, the web support page).
 * Anything else — a WhatsApp thread, which is also `GENERAL_SUPPORT` but is not the web
 * support thread (§26.8) — opens by its own id, so every row in the list leads somewhere.
 */
export function conversationHref(conversation: Conversation): string {
  if (conversation.channel === ConversationChannel.WHATSAPP) {
    return ROUTES.PORTAL.CHAT_THREAD(conversation.id);
  }
  if (conversation.verificationId) {
    return ROUTES.PORTAL.VERIFICATION_MESSAGES(conversation.verificationId);
  }
  if (conversation.type === ConversationType.GENERAL_SUPPORT) {
    return ROUTES.PORTAL.SUPPORT;
  }
  return ROUTES.PORTAL.CHAT_THREAD(conversation.id);
}

/** A thread's name in the customer's list and on its own page. */
export function conversationTitle(conversation: Conversation): string {
  if (conversation.channel === ConversationChannel.WHATSAPP) return "WhatsApp chat";
  if (conversation.type === ConversationType.GENERAL_SUPPORT) return "General support";
  return conversation.subject ?? "Verification chat";
}

/** The line under the title that tells two similar threads apart. */
export function conversationSubtitle(conversation: Conversation): string {
  // The WhatsApp thread is keyed on the customer's number, which is the clearest way to tell
  // it apart from the web support thread in the same list.
  if (conversation.channel === ConversationChannel.WHATSAPP) {
    return conversation.externalRef ?? "WhatsApp enquiry";
  }
  if (conversation.type === ConversationType.CUSTOMER_ADMIN) return "You and the Veriprops team";
  if (conversation.type === ConversationType.GENERAL_SUPPORT) return "Account & billing help";
  return "Verification thread";
}

// ── Admin Conversations inbox (§16.5) ──────────────────────────────────

const CASE_THREAD_LABELS: Record<ConversationType, string> = {
  [ConversationType.CUSTOMER_ADMIN]: "Case · customer thread",
  [ConversationType.ADMIN_AGENT]: "Case · agent thread",
  [ConversationType.GENERAL_SUPPORT]: "Web support",
};

/**
 * A thread's name in the admin inbox. Admins are not members of what they work, so the
 * name is who it belongs to (the backend's owner, set for support threads), else the
 * number a WhatsApp enquiry came from, else the case thread's subject.
 */
export function adminConversationTitle(conversation: Conversation): string {
  if (conversation.ownerName) return conversation.ownerName;
  if (conversation.channel === ConversationChannel.WHATSAPP) {
    return conversation.externalRef ?? "WhatsApp enquiry";
  }
  if (conversation.type === ConversationType.GENERAL_SUPPORT) return "Web support";
  return conversation.subject ?? CASE_THREAD_LABELS[conversation.type];
}

/** The admin inbox's second line: what kind of thread it is, or how to reach its owner. */
export function adminConversationSubtitle(conversation: Conversation): string {
  if (conversation.channel === ConversationChannel.WHATSAPP) {
    // Titled by the owner once linked, so the number moves down here.
    return conversation.ownerName
      ? (conversation.externalRef ?? "WhatsApp")
      : "Not linked to an account";
  }
  if (conversation.type === ConversationType.GENERAL_SUPPORT) {
    return conversation.ownerEmail ?? CASE_THREAD_LABELS[ConversationType.GENERAL_SUPPORT];
  }
  return CASE_THREAD_LABELS[conversation.type];
}

/** The case page behind a verification thread, for the admin who needs its context. */
export function adminCaseMessagesHref(conversation: Conversation): string | null {
  return conversation.verificationId
    ? ROUTES.ADMIN.VERIFICATION_MESSAGES(conversation.verificationId)
    : null;
}

const READ_ONLY_NOTICES: Record<ConversationReadOnlyReason, string> = {
  [ConversationReadOnlyReason.NUMBER_UNLINKED]:
    "This WhatsApp number is no longer linked to your account, so this conversation is read-only.",
};

/** The words shown in place of the composer for a backend-supplied read-only reason. */
export function readOnlyNotice(reason: ConversationReadOnlyReason): string {
  return READ_ONLY_NOTICES[reason];
}
