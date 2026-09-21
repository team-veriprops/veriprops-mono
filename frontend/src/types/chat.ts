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
 * Which surface a thread originated on / a message arrived on (§26.3.3 source labeling).
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
 * What a customer sent, when it was not text (§26.6.3). Set only on WhatsApp-sourced
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

/**
 * How far a message got on the customer's WhatsApp (D92) — Meta's receipts, plus CANCELLED
 * for a queued reply the customer read on the website first, so it never went to the phone.
 */
export enum ChannelDeliveryStatus {
  SENT = "SENT",
  DELIVERED = "DELIVERED",
  READ = "READ",
  FAILED = "FAILED",
  CANCELLED = "CANCELLED",
}

/** Server-owned: every human message is CHAT; only the platform writes SYSTEM_AUTO. */
export enum MessageKind {
  CHAT = "CHAT",
  SYSTEM_AUTO = "SYSTEM_AUTO",
}

export enum SenderKind {
  CUSTOMER = "CUSTOMER",
  ADMIN = "ADMIN",
  AGENT = "AGENT",
  SYSTEM = "SYSTEM",
}

/** Why a member may read a thread but no longer write to it. */
export enum ConversationReadOnlyReason {
  NUMBER_UNLINKED = "NUMBER_UNLINKED",
}

/** The facets of the admin Conversations inbox (§16.5) — each a server-side scope. */
export enum AdminInboxFilter {
  SUPPORT = "SUPPORT",
  WHATSAPP = "WHATSAPP",
  CASES = "CASES",
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
  /**
   * Backend-derived for this viewer: the history stays readable but the composer is
   * closed (e.g. the WhatsApp number behind the thread was unlinked, §26.4.4).
   */
  readOnly?: boolean;
  readOnlyReason?: ConversationReadOnlyReason | null;
  /** The account a support thread belongs to — set only in the admin inbox. */
  ownerName?: string | null;
  ownerEmail?: string | null;
  /**
   * A web turn is waiting on the assistant's intent model (D93): the thread shows the
   * assistant typing, and the client asks for the turn (`POST .../assistant/turn`). A
   * reload mid-turn sees this on the conversation list/opener and can recover by asking.
   */
  assistantPending?: boolean;
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
  sender: ChatSender;
  heldNotice?: string | null;
  dateCreated: string;
  deliveredAt?: string | null;
  /** What arrived, when it was not text (§26.6.3). */
  mediaKind?: InboundKind | null;
  /**
   * Chat-borne media, which the evidence rule (§26.1.6) keeps out of the verification
   * file. Derived by the backend from `mediaKind` — never a second thing to keep in sync.
   */
  unofficialMedia?: boolean;
  /**
   * In the thread but not yet sent over WhatsApp, because it was typed outside Meta's
   * 24-hour window (§26.7). It goes out on the customer's next message.
   */
  pendingChannelDelivery?: boolean;
  /** Console only (backend-derived per viewer): the WhatsApp delivery ticks. */
  channelStatus?: ChannelDeliveryStatus | null;
  /** Customer only: an admin has read the thread past this message of theirs. */
  seenBySupport?: boolean;
  /**
   * On a send's response only (D93): the assistant's inline answer to this message, when
   * the deterministic steps could answer it without the intent model.
   */
  assistantReply?: ChatMessage | null;
  /** On a send's response only: the answer needs the intent model — call the turn endpoint. */
  assistantPending?: boolean;
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

// ── The assistant (PRD §26.6, §16.7, D57, D93) ────────────────────────
//
// One assistant answers on every surface it is enabled for — a WhatsApp thread, a web
// support thread, a case's customer thread — keyed by conversation rather than by number.

/** Who is answering a thread. Sticky once a human joins (D57). */
export enum BotMode {
  BOT = "BOT",
  HUMAN = "HUMAN",
}

/** A multi-step conversation the assistant is part-way through; null between flows. */
export enum BotFlow {
  WELCOME = "WELCOME",
  STATUS = "STATUS",
  INTAKE = "INTAKE",
  UPLOAD = "UPLOAD",
  PAY = "PAY",
  REPORT = "REPORT",
}

/** Why a conversation went to a person (§26.6.2, §26.10). */
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

/** The assistant's state for one conversation, as the console shows it. */
export interface AssistantSession {
  conversationId: string;
  /** False for a thread the assistant never answers (an admin↔agent thread) — the console
   * shows nothing rather than a stale BOT/HUMAN mode for a thread with no assistant at all. */
  enabled: boolean;
  /** Set only on a WhatsApp thread. */
  phoneE164?: string | null;
  mode: BotMode;
  modeChangedAt?: string | null;
  currentFlow?: BotFlow | null;
  lastInboundAt?: string | null;
  /**
   * Whether Meta's 24-hour service window is still open (§26.7) — WhatsApp only, `null`
   * elsewhere. Closed means a reply typed now is queued behind a `window_reopen` template
   * rather than delivered as written, which an agent needs to know *before* they write it.
   */
  windowOpen?: boolean | null;
  lastEscalationReason?: EscalationReason | null;
  lastEscalatedAt?: string | null;
}

/** Whether the channel is wired for live traffic (§26.11). Never carries a credential. */
export interface AssistantReadiness {
  whatsappProvider: string;
  intentProvider: string;
  intentModel: string;
  intentConfigured: boolean;
  humanModeSessions: number;
}
