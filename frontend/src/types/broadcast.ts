// Broadcast types — mirror backend camelCase DTOs (PRD §18.1, D37).

export enum BroadcastAudience {
  ALL = "ALL",
  ADMINS = "ADMINS",
  CUSTOMERS = "CUSTOMERS",
  AGENTS = "AGENTS",
}

export enum BroadcastStatus {
  DRAFT = "DRAFT",
  SCHEDULED = "SCHEDULED",
  /** Claimed; the fan-out is reaching the audience page by page. */
  SENDING = "SENDING",
  SENT = "SENT",
  CANCELLED = "CANCELLED",
  /** One fan-out page kept failing; everyone reached before it keeps their notice. */
  FAILED = "FAILED",
}

/** What an admin may do to a broadcast — the backend lists them per row (`allowedActions`). */
export enum BroadcastAction {
  SEND = "SEND",
  CANCEL = "CANCEL",
}

export interface Broadcast {
  id: string;
  audience: BroadcastAudience;
  subject: string;
  body: string;
  status: BroadcastStatus;
  scheduledAt?: string;
  sentAt?: string;
  /** The audience size, counted when sending began. */
  recipientCount: number;
  /** Recipients the fan-out has reached so far. */
  recipientsEnqueued: number;
  allowedActions: BroadcastAction[];
  dateCreated: string;
}

export interface BroadcastPreview {
  audience: BroadcastAudience;
  recipientCount: number;
}

export interface ComposeBroadcastRequest {
  audience: BroadcastAudience;
  subject: string;
  body: string;
  scheduledAt?: string;
}
