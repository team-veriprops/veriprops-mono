// NDPA data-erasure request models (PRD §18.1, §19.1). Mirrors
// app/domain/compliance/erasure/models.py — camelCase on the wire.

export enum ErasureRequestStatus {
  PENDING = "PENDING",
  APPROVED = "APPROVED",
  EXECUTED = "EXECUTED",
  REJECTED = "REJECTED",
}

export interface DataErasureRequest {
  id: string;
  subjectUserId: string;
  requestedByUserId: string;
  reason?: string | null;
  status: ErasureRequestStatus;
  slaDueAt?: string | null;
  reviewedAt?: string | null;
  decisionNote?: string | null;
  executedAt?: string | null;
  dateCreated: string;
}
