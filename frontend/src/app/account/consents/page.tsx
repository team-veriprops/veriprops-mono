"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { httpClient } from "@/containers";
import { Download, Loader2 } from "lucide-react";

interface ConsentHistoryItem {
  documentType: string;
  consentVersion: string;
  acceptedAt: string;
  ipAddress: string | null;
  deviceFingerprint: string | null;
}

interface ConsentHistoryPage {
  items: ConsentHistoryItem[];
  total: number;
  page: number;
  pageSize: number;
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

const TYPE_LABELS: Record<string, string> = {
  TERMS_OF_SERVICE: "Terms of Service",
  PRIVACY_POLICY: "Privacy Policy",
  AGENT_TERMS: "Agent Terms",
  VERIFICATION_CONSENT: "Verification Consent",
};

export default function ConsentsPage() {
  const [page, setPage] = useState(0);

  const { data, isLoading, error } = useQuery<{ data: ConsentHistoryPage }>({
    queryKey: ["account", "consents", page],
    queryFn: () => httpClient.get(`/account/consents/history?page=${page}&page_size=20`),
    staleTime: 60_000,
  });

  const history = (data as any)?.data ?? null;

  const handleDownload = () => {
    window.open("/api/account/consents/history/download", "_blank");
  };

  return (
    <div className="max-w-2xl mx-auto px-4 py-10">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Consent History</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            All agreements you have accepted on Veriprops
          </p>
        </div>
        <button
          onClick={handleDownload}
          className="flex items-center gap-1.5 text-sm text-indigo-600 hover:text-indigo-800 border border-indigo-200 rounded px-3 py-1.5"
          style={{ cursor: "pointer" }}
        >
          <Download className="h-4 w-4" />
          Download CSV
        </button>
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="h-6 w-6 animate-spin text-indigo-500" />
        </div>
      )}

      {error && (
        <p className="text-sm text-red-600">Unable to load consent history.</p>
      )}

      {history && history.items.length === 0 && (
        <p className="text-sm text-gray-400 italic">No consent records found.</p>
      )}

      {history && history.items.length > 0 && (
        <>
          <div className="divide-y divide-gray-100 rounded-lg border border-gray-200">
            {history.items.map((item: ConsentHistoryItem, i: number) => (
              <div key={i} className="px-4 py-3 flex items-start justify-between gap-4">
                <div>
                  <p className="text-sm font-medium text-gray-900">
                    {TYPE_LABELS[item.documentType] ?? item.documentType}
                  </p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    Version {item.consentVersion}
                    {item.ipAddress ? ` · ${item.ipAddress}` : ""}
                  </p>
                </div>
                <p className="text-xs text-gray-400 shrink-0">{formatDate(item.acceptedAt)}</p>
              </div>
            ))}
          </div>

          {history.total > history.pageSize && (
            <div className="flex items-center justify-between mt-4 text-sm text-gray-500">
              <button
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
                style={{ cursor: page === 0 ? "default" : "pointer" }}
                className="disabled:opacity-40"
              >
                Previous
              </button>
              <span>
                Page {page + 1} of {Math.ceil(history.total / history.pageSize)}
              </span>
              <button
                onClick={() => setPage((p) => p + 1)}
                disabled={(page + 1) * history.pageSize >= history.total}
                style={{ cursor: (page + 1) * history.pageSize >= history.total ? "default" : "pointer" }}
                className="disabled:opacity-40"
              >
                Next
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
