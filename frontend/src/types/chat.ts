/**
 * Communication-layer types (PRD §11) — camelCase mirrors of the backend
 * `app/domain/communication` DTOs. Backend is the source of truth for the fraud-hold
 * state, the Chat unread counter, and the customer-safe sender projection (§11.3).
 */

export enum ConversationType {
  CUSTOMER_ADMIN = "CUSTOMER_ADMIN",
  ADMIN_AGENT = "ADMIN_AGENT",
  GENERAL_SUPPORT = "GENERAL_SUPPORT",
}

/** §4.7 message lifecycle. */
export enum ChatMessageState {
  PENDING_SCAN = "PENDING_SCAN",
  HELD = "HELD",
  DELIVERED = "DELIVERED",
  BLOCKED = "BLOCKED",
}

export enum MessageKind {
  CHAT = "CHAT",
  SYSTEM_AUTO = "SYSTEM_AUTO",
  CLARIFICATION_REQUEST = "CLARIFICATION_REQUEST",
  CLARIFICATION_RESPONSE = "CLARIFICATION_RESPONSE",
}

export enum ClarificationStatus {
  OPEN = "OPEN",
  ANSWERED = "ANSWERED",
}

export enum SenderKind {
  CUSTOMER = "CUSTOMER",
  ADMIN = "ADMIN",
  AGENT = "AGENT",
  SYSTEM = "SYSTEM",
}

export interface Conversation {
  id: string;
  type: ConversationType;
  verificationId?: string | null;
  subject?: string | null;
  lastMessageAt?: string | null;
  closed: boolean;
  unread: number;
}

/** Customer-safe sender identity (§11.3) — first name + avatar only for agents. */
export interface ChatSender {
  userId?: string | null;
  kind: SenderKind;
  firstName?: string | null;
  role?: string | null;
  avatarUrl?: string | null;
}

export interface ChatMessage {
  id: string;
  conversationId: string;
  body: string;
  taskId?: string | null;
  state: ChatMessageState;
  messageKind: MessageKind;
  clarificationStatus?: ClarificationStatus | null;
  sender: ChatSender;
  heldNotice?: string | null;
  dateCreated: string;
  deliveredAt?: string | null;
}

/** Admin hold-review queue item (§11.2). */
export interface HeldMessage {
  id: string;
  conversationId: string;
  conversationType?: string | null;
  verificationId?: string | null;
  senderUserId?: string | null;
  senderKind: SenderKind;
  body: string;
  flaggedCategories: string[];
  heldAt?: string | null;
  dateCreated: string;
}
