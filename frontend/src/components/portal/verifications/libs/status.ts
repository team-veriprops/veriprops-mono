import { VerificationStatus } from "./verification-service";

export const STATUS_LABELS: Record<VerificationStatus, string> = {
  DRAFT: "Draft",
  SUBMITTED: "Submitted",
  PAYMENT_PENDING: "Payment Pending",
  PAID: "Paid",
  IN_PROGRESS: "In Progress",
  UNDER_REVIEW: "Under Review",
  COMPLETED: "Completed",
  DISPUTED: "Disputed",
  CANCELLED: "Cancelled",
  REFUNDED: "Refunded",
  FAILED: "Failed",
};

export const STATUS_COLORS: Record<VerificationStatus, { bg: string; text: string }> = {
  DRAFT: { bg: "rgba(0,13,34,0.06)", text: "var(--brand-on-surface-variant)" },
  SUBMITTED: { bg: "rgba(59,130,246,0.1)", text: "#3b82f6" },
  PAYMENT_PENDING: { bg: "rgba(245,158,11,0.1)", text: "#d97706" },
  PAID: { bg: "rgba(63,102,83,0.1)", text: "var(--brand-viridian)" },
  IN_PROGRESS: { bg: "rgba(59,130,246,0.1)", text: "#3b82f6" },
  UNDER_REVIEW: { bg: "rgba(168,85,247,0.1)", text: "#9333ea" },
  COMPLETED: { bg: "rgba(63,102,83,0.15)", text: "var(--brand-viridian)" },
  DISPUTED: { bg: "rgba(239,68,68,0.1)", text: "#ef4444" },
  CANCELLED: { bg: "rgba(0,13,34,0.06)", text: "var(--brand-on-surface-variant)" },
  REFUNDED: { bg: "rgba(107,114,128,0.1)", text: "#6b7280" },
  FAILED: { bg: "rgba(239,68,68,0.1)", text: "#ef4444" },
};

export const ACTIVE_STATUSES: VerificationStatus[] = [
  "PAYMENT_PENDING",
  "PAID",
  "IN_PROGRESS",
  "UNDER_REVIEW",
];

export const COMPLETED_STATUSES: VerificationStatus[] = ["COMPLETED"];

export const CANCELLED_STATUSES: VerificationStatus[] = ["CANCELLED", "REFUNDED", "FAILED"];
