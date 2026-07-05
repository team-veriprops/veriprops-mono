// Admin verification control-panel types (PRD §6, §6a) — mirror backend camelCase
// DTOs at app/domain/verification/admin. Backend is the source of truth for status,
// SLA health, task state, commissions and chargebacks.
import { TransactionCurrency } from "@/types/models";
import { AgentRole } from "@/types/agent";
import {
  PaymentMethodKind,
  PaymentStatus,
  PropertyKind,
  VerificationStatus,
  VerificationTier,
} from "@/types/verification";

export enum TaskState {
  PENDING = "PENDING",
  ASSIGNED = "ASSIGNED",
  ACCEPTED = "ACCEPTED",
  IN_PROGRESS = "IN_PROGRESS",
  SUBMITTED = "SUBMITTED",
  REJECTED = "REJECTED",
  APPROVED = "APPROVED",
}

export enum TaskAssignmentMode {
  MANUAL = "MANUAL",
  BROADCAST = "BROADCAST",
}

export enum SlaHealth {
  ON_TRACK = "ON_TRACK",
  AT_RISK = "AT_RISK",
  OVERDUE = "OVERDUE",
  NONE = "NONE",
}

export enum CommissionStatus {
  CLEARING = "CLEARING",
  AVAILABLE = "AVAILABLE",
  FROZEN = "FROZEN",
  REVERSED = "REVERSED",
}

export enum ChargebackStatus {
  FLAGGED = "FLAGGED",
  REBUTTAL_SUBMITTED = "REBUTTAL_SUBMITTED",
  WON = "WON",
  LOST = "LOST",
}

export enum AdminNoteCategory {
  OPERATIONAL = "OPERATIONAL",
  QUALITY = "QUALITY",
  RISK = "RISK",
  HANDOVER = "HANDOVER",
}

export interface VerificationSummary {
  id: string;
  vid: string;
  customerId: string;
  tier?: VerificationTier;
  status: VerificationStatus;
  paused: boolean;
  stateRegion?: string;
  slaDueDate?: string;
  slaHealth: SlaHealth;
  businessDaysRemaining?: number;
  dateCreated: string;
}

/** Admin operations home summary (§6) — backend-owned queue health. */
export interface AdminDashboard {
  total: number;
  statusCounts: Partial<Record<VerificationStatus, number>>;
  overdue: number;
  unassignedPoolTasks: number;
  pendingAgentApplications: number;
  openChargebacks: number;
  recent: VerificationSummary[];
}

export interface AdminPropertyDto {
  id: string;
  propertyType: PropertyKind;
  address?: string;
  landmark?: string;
  state?: string;
  lga?: string;
  latitude?: number;
  longitude?: number;
}

export interface TaskDto {
  id: string;
  verificationId: string;
  role: AgentRole;
  tier: VerificationTier;
  state: TaskState;
  assignedAgentId?: string;
  assignmentMode?: TaskAssignmentMode;
  inPool: boolean;
  poolExpiresAt?: string;
  acceptDeadlineAt?: string;
  declineCount: number;
  remoteBonusMinor?: number;
  assignedAt?: string;
  acceptedAt?: string;
  submittedAt?: string;
  approvedAt?: string;
}

export interface AdminNoteDto {
  id: string;
  verificationId: string;
  authorId: string;
  category: AdminNoteCategory;
  body: string;
  pinned: boolean;
  dateCreated: string;
}

export interface AdminPaymentDto {
  id: string;
  verificationId: string;
  txRef: string;
  method: PaymentMethodKind;
  status: PaymentStatus;
  amountMinor: number;
  currency: TransactionCurrency;
  chargeCurrency?: TransactionCurrency;
  chargeAmountMinor?: number;
  checkoutUrl?: string;
  dateCreated: string;
}

export interface CommissionDto {
  id: string;
  verificationId: string;
  taskId?: string;
  agentId: string;
  role: AgentRole;
  tier: VerificationTier;
  amountMinor: number;
  currency: TransactionCurrency;
  status: CommissionStatus;
  clearingUntil?: string;
  dateCreated: string;
}

export interface ChargebackDto {
  id: string;
  paymentId: string;
  verificationId: string;
  status: ChargebackStatus;
  reason?: string;
  amountMinor?: number;
  currency: TransactionCurrency;
  rebuttalPack?: Record<string, unknown>;
  resolvedAt?: string;
  dateCreated: string;
}

export interface VerificationDetail {
  summary: VerificationSummary;
  property?: AdminPropertyDto;
  tasks: TaskDto[];
  notes: AdminNoteDto[];
  payments: AdminPaymentDto[];
  commissions: CommissionDto[];
  chargebacks: ChargebackDto[];
  progressPercent: number;
  requiredTaskCount: number;
  approvedTaskCount: number;
}

export interface VerificationListFilters {
  status?: VerificationStatus;
  tier?: VerificationTier;
  stateRegion?: string;
  overdueOnly?: boolean;
  query?: string;
}
