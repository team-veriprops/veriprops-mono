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
  SENT = "SENT",
  CANCELLED = "CANCELLED",
}

export interface Broadcast {
  id: string;
  audience: BroadcastAudience;
  subject: string;
  body: string;
  status: BroadcastStatus;
  scheduledAt?: string;
  sentAt?: string;
  recipientCount: number;
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
