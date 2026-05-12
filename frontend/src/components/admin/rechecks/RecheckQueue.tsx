"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle, XCircle, Loader2 } from "lucide-react";
import { httpClient } from "@/containers";
import { getErrorMessage } from "@lib/utils";
import { useState } from "react";

interface RecheckRequest {
  id: string;
  verificationId: string;
  reason: string;
  scopeRoles: string[];
  status: string;
  requestedBy: string;
  price: number | null;
  dateCreated: string;
}

const qKey = ["admin", "rechecks"];

export default function RecheckQueue() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: qKey,
    queryFn: () => httpClient.get("/api/admin/rechecks"),
  });
  const requests: RecheckRequest[] = (data as any)?.data ?? [];
  const [error, setError] = useState<string | null>(null);

  const approve = useMutation({
    mutationFn: (id: string) => httpClient.post(`/api/admin/rechecks/${id}/approve`),
    onSuccess: () => qc.invalidateQueries({ queryKey: qKey }),
    onError: (e: any) => setError(getErrorMessage(e)),
  });

  const reject = useMutation({
    mutationFn: (id: string) =>
      httpClient.post(`/api/admin/rechecks/${id}/reject`, { reason: "Does not meet criteria." }),
    onSuccess: () => qc.invalidateQueries({ queryKey: qKey }),
    onError: (e: any) => setError(getErrorMessage(e)),
  });

  if (isLoading) {
    return (
      <div className="flex justify-center py-10">
        <Loader2 className="h-5 w-5 animate-spin text-indigo-500" />
      </div>
    );
  }

  return (
    <div data-testid="recheck-queue">
      {error && (
        <div className="mb-4 rounded bg-red-50 border border-red-200 px-4 py-2 text-sm text-red-700">
          {error}
        </div>
      )}
      {requests.length === 0 ? (
        <p className="text-center text-gray-500 py-10">No pending re-check requests.</p>
      ) : (
        <div className="space-y-4">
          {requests.map((req) => (
            <div
              key={req.id}
              className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm"
              data-testid="recheck-request-item"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-gray-900 truncate">
                    Verification: {req.verificationId}
                  </p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    Requested: {new Date(req.dateCreated).toLocaleDateString()}
                  </p>
                  <p className="text-sm text-gray-700 mt-2">{req.reason}</p>
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {req.scopeRoles.map((role) => (
                      <span
                        key={role}
                        className="rounded-full bg-blue-50 border border-blue-200 px-2 py-0.5 text-xs text-blue-700"
                      >
                        {role}
                      </span>
                    ))}
                  </div>
                  {req.price !== null && (
                    <p className="text-xs font-medium text-indigo-700 mt-2">
                      Price: ₦{req.price.toLocaleString()}
                    </p>
                  )}
                </div>
                {req.status === "PENDING" && (
                  <div className="flex gap-2 flex-shrink-0">
                    <button
                      type="button"
                      onClick={() => approve.mutate(req.id)}
                      disabled={approve.isPending}
                      style={{ cursor: "pointer" }}
                      className="inline-flex items-center gap-1 rounded-md border border-green-300 bg-green-50 px-3 py-1.5 text-xs font-medium text-green-700 hover:bg-green-100"
                      data-testid="recheck-approve-button"
                    >
                      <CheckCircle className="h-3.5 w-3.5" />
                      Approve
                    </button>
                    <button
                      type="button"
                      onClick={() => reject.mutate(req.id)}
                      disabled={reject.isPending}
                      style={{ cursor: "pointer" }}
                      className="inline-flex items-center gap-1 rounded-md border border-red-300 bg-red-50 px-3 py-1.5 text-xs font-medium text-red-700 hover:bg-red-100"
                      data-testid="recheck-reject-button"
                    >
                      <XCircle className="h-3.5 w-3.5" />
                      Reject
                    </button>
                  </div>
                )}
                {req.status !== "PENDING" && (
                  <span
                    className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                      req.status === "APPROVED"
                        ? "bg-green-100 text-green-700"
                        : "bg-gray-100 text-gray-600"
                    }`}
                  >
                    {req.status}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
