"use client";

import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { httpClient } from "@/containers";
import { useState } from "react";
import DisputeResolutionForm from "./DisputeResolutionForm";

interface Dispute {
  id: string;
  verificationId: string;
  disputeType: string;
  description: string;
  status: string;
  submittedBy: string;
  submittedAt: string;
}

const qKey = ["admin", "disputes"];

export default function DisputeQueue() {
  const { data, isLoading } = useQuery({
    queryKey: qKey,
    queryFn: () => httpClient.get("/api/admin/disputes"),
  });
  const disputes: Dispute[] = (data as any)?.data ?? [];
  const [resolving, setResolving] = useState<string | null>(null);

  if (isLoading) {
    return (
      <div className="flex justify-center py-10">
        <Loader2 className="h-5 w-5 animate-spin text-indigo-500" />
      </div>
    );
  }

  return (
    <div data-testid="dispute-queue">
      {resolving && (
        <DisputeResolutionForm
          disputeId={resolving}
          open={true}
          onClose={() => setResolving(null)}
        />
      )}

      {disputes.length === 0 ? (
        <p className="text-center text-gray-500 py-10">No pending disputes.</p>
      ) : (
        <div className="space-y-4">
          {disputes.map((dispute) => (
            <div
              key={dispute.id}
              className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm"
              data-testid="dispute-item"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-semibold text-gray-900 truncate">
                      {dispute.disputeType.replace(/_/g, " ")}
                    </p>
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                        dispute.status === "PENDING"
                          ? "bg-orange-100 text-orange-700"
                          : "bg-gray-100 text-gray-600"
                      }`}
                    >
                      {dispute.status}
                    </span>
                  </div>
                  <p className="text-xs text-gray-500 mt-0.5">
                    Verification: {dispute.verificationId} · Submitted:{" "}
                    {new Date(dispute.submittedAt).toLocaleDateString()}
                  </p>
                  <p className="text-sm text-gray-700 mt-2 line-clamp-3">{dispute.description}</p>
                </div>
                {dispute.status === "PENDING" && (
                  <button
                    type="button"
                    onClick={() => setResolving(dispute.id)}
                    style={{ cursor: "pointer" }}
                    className="flex-shrink-0 rounded-md border border-indigo-300 bg-indigo-50 px-3 py-1.5 text-xs font-medium text-indigo-700 hover:bg-indigo-100"
                    data-testid="dispute-resolve-button"
                  >
                    Resolve
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
