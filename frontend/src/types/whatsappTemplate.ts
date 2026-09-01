/**
 * Meta template registry types (PRD §7.7) — camelCase mirrors of the backend
 * `app/domain/channel/whatsapp/template` DTOs.
 *
 * Backend owns every fact here, including what the seven templates *are*: the definitions
 * are code-owned on the backend, and this page renders what the registry returns. There
 * is deliberately nothing to edit.
 */

export enum WhatsAppTemplateStatus {
  /** Ours, not Meta's: declared in code, never submitted. */
  NOT_FOUND = "NOT_FOUND",
  APPROVED = "APPROVED",
  PENDING = "PENDING",
  IN_APPEAL = "IN_APPEAL",
  REJECTED = "REJECTED",
  PENDING_DELETION = "PENDING_DELETION",
  DELETED = "DELETED",
  DISABLED = "DISABLED",
  PAUSED = "PAUSED",
  LIMIT_EXCEEDED = "LIMIT_EXCEEDED",
  ARCHIVED = "ARCHIVED",
}

export interface WhatsAppTemplate {
  name: string;
  category: string;
  language: string;
  status: WhatsAppTemplateStatus;
  rejectionReason?: string | null;
  lastSyncedAt?: string | null;
  /** Ordered parameter names, so the page shows how the template is filled. */
  parameters: string[];
}

export interface WhatsAppTemplateSyncResult {
  synced: number;
  approved: number;
  missing: number;
}
