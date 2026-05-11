"use client";

import { ShieldCheck, Download } from "lucide-react";
import TrustScoreBadge from "@components/shared/TrustScoreBadge";

interface Props {
  vid: string;
  version: string;
  tier: string;
  completedAt: string | null;
  trustScore: number | null;
  onDownloadPdf: () => void;
  pdfLoading: boolean;
}

export default function ReportHeader({ vid, version, tier, completedAt, trustScore, onDownloadPdf, pdfLoading }: Props) {
  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-6 w-6 text-green-600" />
            <h1 className="text-2xl font-semibold text-gray-900 font-mono">{vid}</h1>
          </div>
          <div className="flex items-center gap-3 mt-1 flex-wrap">
            <span className="text-sm text-gray-500">{tier} Verification</span>
            <span className="text-xs text-gray-400">{version}</span>
            {completedAt && (
              <span className="text-xs text-gray-400">
                {new Date(completedAt).toLocaleDateString()}
              </span>
            )}
            {trustScore !== null && (
              <TrustScoreBadge score={trustScore} size="sm" />
            )}
          </div>
        </div>
        <button
          onClick={onDownloadPdf}
          disabled={pdfLoading}
          style={{ cursor: pdfLoading ? "not-allowed" : "pointer" }}
          className="flex items-center gap-2 rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-60 shrink-0"
        >
          <Download className="h-4 w-4" />
          {pdfLoading ? "Generating…" : "Download PDF"}
        </button>
      </div>
      <div className="h-px bg-gray-200" />
    </div>
  );
}
