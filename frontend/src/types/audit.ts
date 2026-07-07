// Audit read models (PRD §19.1–19.3). Mirrors app/domain/audit/models.py — camelCase on the wire.

/** PII-safe transition event shown to customers and agents (no actorId). */
export interface AuditActivityEvent {
  action: string;
  occurredAt: string;
  fromState?: string | null;
  toState?: string | null;
  details?: Record<string, unknown> | null;
}

export interface AuditActivityPage {
  items: AuditActivityEvent[];
  total: number;
  page: number;
  pageSize: number;
}

/** Full audit row for the admin action log / export (carries actorId + IP). */
export interface AuditPackRow {
  id: string;
  actorId?: string | null;
  action: string;
  resourceType: string;
  resourceId: string;
  fromState?: string | null;
  toState?: string | null;
  occurredAt: string;
  ipAddress?: string | null;
  details?: Record<string, unknown> | null;
}

export interface AdminActionLogPage {
  items: AuditPackRow[];
  total: number;
  page: number;
  pageSize: number;
}

/** The admin-mutation action types surfaced in the action-log filter (§19.6). */
export const ADMIN_ACTION_TYPES = [
  "ADMIN_INVITED",
  "ADMIN_INVITE_ACCEPTED",
  "ADMIN_ROLE_CHANGED",
  "ADMIN_CONFIG_CHANGED",
  "AGENT_APPLICATION_APPROVED",
  "AGENT_APPLICATION_REJECTED",
  "WIRE_PROOF_CONFIRMED",
  "DATA_ERASURE_APPROVED",
  "DATA_ERASURE_EXECUTED",
  "DATA_ERASURE_REJECTED",
] as const;
