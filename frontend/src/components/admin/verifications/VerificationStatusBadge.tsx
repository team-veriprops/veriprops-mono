"use client";

import type { VerificationStatus } from "../libs/admin-service";

const BADGE_STYLES: Record<VerificationStatus, string> = {
  DRAFT: "bg-gray-100 text-gray-700",
  PAID: "bg-blue-100 text-blue-700",
  IN_PROGRESS: "bg-yellow-100 text-yellow-800",
  UNDER_REVIEW: "bg-purple-100 text-purple-700",
  COMPLETED: "bg-green-100 text-green-700",
  CANCELLED: "bg-red-100 text-red-700",
  FAILED: "bg-red-200 text-red-800",
  PAUSED: "bg-orange-100 text-orange-700",
  FLAGGED: "bg-pink-100 text-pink-700",
};

export default function VerificationStatusBadge({ status }: { status: VerificationStatus }) {
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${BADGE_STYLES[status] ?? "bg-gray-100 text-gray-700"}`}
    >
      {status.replace("_", " ")}
    </span>
  );
}
