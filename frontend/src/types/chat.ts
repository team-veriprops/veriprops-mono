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

/**
 * Which surface a thread originated on / a message arrived on (§7.3.3 source labeling).
 * Orthogonal to ConversationType and SenderKind: the same customer can speak from either
 * surface, and the console shows which one so a reply goes back the right way.
 */
export enum ConversationChannel {
  WEB = "WEB",
  WHATSAPP = "WHATSAPP",
}

export enum MessageSource {
  WEB = "WEB",
  WHATSAPP = "WHATSAPP",
}

/**
 * What a customer sent, when it was not text (§7.6.3). Set only on WhatsApp-sourced
 * messages; its presence is what makes a message "unofficial" under the evidence rule.
 */
export enum InboundKind {
  TEXT = "TEXT",
  INTERACTIVE = "INTERACTIVE",
  IMAGE = "IMAGE",
  DOCUMENT = "DOCUMENT",
  VIDEO = "VIDEO",
  AUDIO = "AUDIO",
  STICKER = "STICKER",
  LOCATION = "LOCATION",
  CONTACTS = "CONTACTS",
  UNSUPPORTED = "UNSUPPORTED",
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
  channel?: ConversationChannel;
  /** The sender's E.164 number for a WhatsApp thread — null for a web thread. */
  externalRef?: string | null;
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
  source?: MessageSource;
  clarificationStatus?: ClarificationStatus | null;
  sender: ChatSender;
  heldNotice?: string | null;
  dateCreated: string;
  deliveredAt?: string | null;
  /** What arrived, when it was not text (§7.6.3). */
  mediaKind?: InboundKind | null;
  /**
   * Chat-borne media, which the evidence rule (§7.1.6) keeps out of the verification
   * file. Derived by the backend from `mediaKind` — never a second thing to keep in sync.
   */
  unofficialMedia?: boolean;
  /**
   * In the thread but not yet sent over WhatsApp, because it was typed outside Meta's
   * 24-hour window (§7.7). It goes out on the customer's next message.
   */
  pendingChannelDelivery?: boolean;
}

/** Admin hold-review queue item (§11.2). */
export interface HeldMessage {
  id: string;
  conversationId: string;
  conversationType?: string | null;
  verificationId?: string | null;
  senderUserId?: string | null;
  senderKind: SenderKind;
  source?: MessageSource;
  body: string;
  flaggedCategories: string[];
  heldAt?: string | null;
  dateCreated: string;
}

// ── WhatsApp bot state (PRD §7.6, D57) ───────────────────────────────

/** Who is answering a WhatsApp thread. Sticky once a human joins (D57). */
export enum BotMode {
  BOT = "BOT",
  HUMAN = "HUMAN",
}

/** A multi-step conversation the bot is part-way through; null between flows. */
export enum BotFlow {
  WELCOME = "WELCOME",
  STATUS = "STATUS",
  INTAKE = "INTAKE",
  UPLOAD = "UPLOAD",
}

/** Why a conversation went to a person (§7.6.2, §7.10). */
export enum EscalationReason {
  EXPLICIT_REQUEST = "EXPLICIT_REQUEST",
  GUARDRAIL_TOPIC = "GUARDRAIL_TOPIC",
  REFUND_OR_CANCELLATION = "REFUND_OR_CANCELLATION",
  UNMATCHED_INTENTS = "UNMATCHED_INTENTS",
  NON_ENGLISH = "NON_ENGLISH",
  CAPABILITY_NOT_OFFERED = "CAPABILITY_NOT_OFFERED",
  VOICE_NOTE = "VOICE_NOTE",
  UNSUPPORTED_MEDIA = "UNSUPPORTED_MEDIA",
  PIPELINE_FAILURE = "PIPELINE_FAILURE",
}

/** The bot's state for one WhatsApp number, as the console shows it. */
export interface BotSession {
  phoneE164: string;
  mode: BotMode;
  modeChangedAt?: string | null;
  currentFlow?: BotFlow | null;
  lastInboundAt?: string | null;
  /**
   * Whether Meta's 24-hour service window is still open on this number (§7.7). Closed
   * means a reply typed now is queued behind a `window_reopen` template rather than
   * delivered as written — which an agent needs to know *before* they write it.
   */
  windowOpen?: boolean;
  lastEscalationReason?: EscalationReason | null;
  lastEscalatedAt?: string | null;
}

/** Whether the channel is wired for live traffic (§7.11). Never carries a credential. */
export interface BotChannelReadiness {
  whatsappProvider: string;
  intentProvider: string;
  intentModel: string;
  intentConfigured: boolean;
  humanModeSessions: number;
}
