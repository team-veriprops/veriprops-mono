"use client";

import { use } from "react";
import { ArrowLeft, Clock, Loader2 } from "lucide-react";
import Link from "next/link";
import { ROUTES } from "@lib/routes";
import { useVerificationActivity } from "@components/portal/verifications/libs/useTrackingQueries";

const ACTION_LABELS: Record<string, string> = {
  VERIFICATION_SUBMITTED: "Verification submitted",
  VERIFICATION_PAID: "Payment received",
  VERIFICATION_STARTED: "Verification started",
  VERIFICATION_UNDER_REVIEW: "Submitted for review",
  VERIFICATION_COMPLETED: "Verification completed",
  VERIFICATION_CANCELLED: "Verification cancelled",
  VERIFICATION_DISPUTED: "Dispute opened",
  TASK_ASSIGNED: "Agent assigned",
  TASK_ACCEPTED: "Agent accepted task",
  TASK_IN_PROGRESS: "Agent marked in progress",
  TASK_SUBMITTED: "Agent submitted report",
  TASK_APPROVED: "Report approved",
  TASK_REJECTED: "Report rejected",
  REPORT_RELEASED: "Report released",
  NOTE_ADDED: "Note added",
};

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function TimelineItem({ action, occurredAt, toState }: { action: string; occurredAt: string; toState: string | null }) {
  const label = ACTION_LABELS[action] ?? action.replace(/_/g, " ").toLowerCase();
  return (
    <div className="flex gap-3">
      <div className="flex flex-col items-center">
        <div className="h-2.5 w-2.5 rounded-full bg-indigo-500 mt-1 shrink-0" />
        <div className="w-px bg-gray-200 flex-1 mt-1" />
      </div>
      <div className="pb-4">
        <p className="text-sm font-medium text-gray-900 capitalize">{label}</p>
        {toState && (
          <p className="text-xs text-gray-500 mt-0.5">
            Status: <span className="font-mono">{toState.replace(/_/g, " ")}</span>
          </p>
        )}
        <p className="text-xs text-gray-400 mt-0.5 flex items-center gap-1">
          <Clock className="h-3 w-3" />
          {formatDate(occurredAt)}
        </p>
      </div>
    </div>
  );
}

export default function VerificationActivityPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { data, isLoading, error } = useVerificationActivity(id, 0);
  const page = (data as any)?.data ?? null;

  return (
    <div className="max-w-xl mx-auto px-4 py-10">
      <Link
        href={ROUTES.PORTAL.VERIFICATION_DETAIL(id)}
        className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 mb-6"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to verification
      </Link>

      <h1 className="text-xl font-semibold text-gray-900 mb-6">Activity Log</h1>

      {isLoading && (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="h-6 w-6 animate-spin text-indigo-500" />
        </div>
      )}

      {error && (
        <p className="text-sm text-red-600">Unable to load activity log.</p>
      )}

      {page && page.items.length === 0 && (
        <p className="text-sm text-gray-400 italic">No activity recorded yet.</p>
      )}

      {page && page.items.length > 0 && (
        <div>
          {page.items.map((event: any, i: number) => (
            <TimelineItem
              key={i}
              action={event.action}
              occurredAt={event.occurredAt}
              toState={event.toState}
            />
          ))}
        </div>
      )}
    </div>
  );
}
