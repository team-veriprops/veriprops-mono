"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { httpClient } from "@/containers";
import { Loader2, CheckCircle, XCircle } from "lucide-react";
import { getErrorMessage } from "@lib/utils";
import { useState } from "react";

export interface FraudFlag {
  id: string;
  messageId: string;
  messageBody: string;
  matchedPatterns: string[];
  reviewed: boolean;
  reviewDecision: string | null;
  reviewerId: string | null;
  reviewedAt: string | null;
  dateCreated: string;
}

const qKey = ["admin", "fraud-flags", "pending"];

async function listPending(): Promise<{ data: FraudFlag[] }> {
  return httpClient.get("/admin/fraud-flags");
}

async function reviewFlag(
  flagId: string,
  decision: "APPROVED" | "REJECTED",
): Promise<void> {
  await httpClient.post(`/admin/fraud-flags/${flagId}/review`, { decision });
}

export default function FraudFlagQueue() {
  const qc = useQueryClient();
  const { data, isLoading, error } = useQuery({ queryKey: qKey, queryFn: listPending });
  const flags: FraudFlag[] = (data as any)?.data ?? [];
  const [actingId, setActingId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const mutate = useMutation({
    mutationFn: ({ id, decision }: { id: string; decision: "APPROVED" | "REJECTED" }) =>
      reviewFlag(id, decision),
    onMutate: ({ id }) => setActingId(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qKey });
      setActingId(null);
    },
    onError: (err) => {
      setActionError(getErrorMessage(err as Error));
      setActingId(null);
    },
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="h-5 w-5 animate-spin text-indigo-600" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="py-8 text-center text-sm text-red-600">
        Failed to load fraud flags.
      </div>
    );
  }

  if (flags.length === 0) {
    return (
      <div className="py-12 text-center text-sm text-gray-400">
        No held messages pending review.
      </div>
    );
  }

  return (
    <div className="space-y-4" data-testid="fraud-flag-queue">
      {actionError && (
        <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">
          {actionError}
        </p>
      )}
      {flags.map((flag) => (
        <div
          key={flag.id}
          className="rounded-lg border border-yellow-200 bg-yellow-50 p-4 space-y-3"
          data-testid="fraud-flag-item"
        >
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-gray-900 break-words">{flag.messageBody}</p>
              <div className="flex flex-wrap gap-1 mt-2">
                {flag.matchedPatterns.map((p) => (
                  <span
                    key={p}
                    className="inline-block text-[10px] px-2 py-0.5 rounded-full bg-orange-100 text-orange-700 font-medium"
                  >
                    {p}
                  </span>
                ))}
              </div>
              <p className="text-xs text-gray-400 mt-1">
                Flagged {new Date(flag.dateCreated).toLocaleString()}
              </p>
            </div>
            <div className="flex flex-col gap-2 shrink-0">
              <button
                onClick={() => mutate.mutate({ id: flag.id, decision: "APPROVED" })}
                disabled={actingId === flag.id}
                style={{ cursor: "pointer" }}
                className="flex items-center gap-1 text-xs px-3 py-1.5 rounded bg-green-600 text-white hover:bg-green-700 disabled:opacity-50"
                data-testid="fraud-flag-approve"
              >
                {actingId === flag.id ? (
                  <Loader2 className="h-3 w-3 animate-spin" />
                ) : (
                  <CheckCircle className="h-3 w-3" />
                )}
                Release
              </button>
              <button
                onClick={() => mutate.mutate({ id: flag.id, decision: "REJECTED" })}
                disabled={actingId === flag.id}
                style={{ cursor: "pointer" }}
                className="flex items-center gap-1 text-xs px-3 py-1.5 rounded bg-red-600 text-white hover:bg-red-700 disabled:opacity-50"
                data-testid="fraud-flag-reject"
              >
                {actingId === flag.id ? (
                  <Loader2 className="h-3 w-3 animate-spin" />
                ) : (
                  <XCircle className="h-3 w-3" />
                )}
                Discard
              </button>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
