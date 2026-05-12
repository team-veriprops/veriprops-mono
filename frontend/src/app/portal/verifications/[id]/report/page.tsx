"use client";

import { use, useState, useCallback } from "react";
import { Loader2, AlertTriangle, Share2, RefreshCw, ArrowUpCircle, Flag } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { httpClient } from "@/containers";
import AccessGateModal from "@components/portal/report/AccessGateModal";
import ReportHeader from "@components/portal/report/ReportHeader";
import ReportSection from "@components/portal/report/ReportSection";
import ReportLegalFooter from "@components/portal/report/ReportLegalFooter";
import ShareModal from "@components/portal/report/ShareModal";
import RecheckModal from "@components/portal/report/RecheckModal";
import TierUpgradeModal from "@components/portal/report/TierUpgradeModal";
import DisputeModal from "@components/portal/report/DisputeModal";

interface ReportData {
  vid: string;
  version: string;
  tier: string;
  completedAt: string | null;
  trustScore: number | null;
  executiveSummary: string | null;
  registryFindings: Record<string, unknown> | null;
  physicalFindings: Record<string, unknown> | null;
  boundaryFindings: Record<string, unknown> | null;
  legalOpinion: Record<string, unknown> | null;
  riskSummary: string | null;
  hasAcknowledged: boolean;
}

function renderKv(data: Record<string, unknown> | null) {
  if (!data || Object.keys(data).length === 0) return <p className="text-gray-400 italic">No data recorded.</p>;
  return (
    <dl className="space-y-1">
      {Object.entries(data).map(([k, v]) => (
        <div key={k} className="flex gap-2">
          <dt className="text-gray-500 capitalize min-w-32">{k.replace(/_/g, " ")}:</dt>
          <dd className="text-gray-800 font-medium">
            {typeof v === "object" ? JSON.stringify(v) : String(v)}
          </dd>
        </div>
      ))}
    </dl>
  );
}

export default function ReportPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [acknowledged, setAcknowledged] = useState(false);
  const [pdfLoading, setPdfLoading] = useState(false);
  const [shareOpen, setShareOpen] = useState(false);
  const [recheckOpen, setRecheckOpen] = useState(false);
  const [upgradeOpen, setUpgradeOpen] = useState(false);
  const [disputeOpen, setDisputeOpen] = useState(false);

  const { data: res, isLoading, error, refetch } = useQuery({
    queryKey: ["portal", "verifications", id, "report"],
    queryFn: () => httpClient.get(`/api/portal/verifications/${id}/report`),
    staleTime: 30_000,
  });
  const report: ReportData | null = (res as any)?.data ?? null;

  const handleAccepted = useCallback(() => {
    setAcknowledged(true);
    refetch();
  }, [refetch]);

  async function handleDownloadPdf() {
    setPdfLoading(true);
    try {
      const resp = await fetch(`/api/portal/verifications/${id}/report/pdf`, { credentials: "include" });
      if (!resp.ok) throw new Error("PDF unavailable");
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `veriprops-report-${id}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setPdfLoading(false);
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin text-indigo-600" />
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="flex items-center gap-2 py-12 text-red-600 justify-center">
        <AlertTriangle className="h-5 w-5" />
        <span className="text-sm">Report not available.</span>
      </div>
    );
  }

  const showGate = !report.hasAcknowledged && !acknowledged;

  return (
    <div className="max-w-2xl mx-auto px-4 py-10 space-y-6">
      {showGate && <AccessGateModal vid={id} onAccepted={handleAccepted} />}

      <ShareModal verificationId={id} open={shareOpen} onClose={() => setShareOpen(false)} />
      <RecheckModal verificationId={id} open={recheckOpen} onClose={() => setRecheckOpen(false)} />
      <TierUpgradeModal verificationId={id} open={upgradeOpen} onClose={() => setUpgradeOpen(false)} />
      <DisputeModal verificationId={id} open={disputeOpen} onClose={() => setDisputeOpen(false)} />

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => setShareOpen(true)}
          style={{ cursor: "pointer" }}
          className="inline-flex items-center gap-1.5 rounded-md border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
          data-testid="report-share-trigger"
        >
          <Share2 className="h-3.5 w-3.5" /> Share
        </button>
        <button
          type="button"
          onClick={() => setRecheckOpen(true)}
          style={{ cursor: "pointer" }}
          className="inline-flex items-center gap-1.5 rounded-md border border-blue-300 px-3 py-1.5 text-xs font-medium text-blue-700 hover:bg-blue-50"
          data-testid="report-recheck-trigger"
        >
          <RefreshCw className="h-3.5 w-3.5" /> Request Re-check
        </button>
        <button
          type="button"
          onClick={() => setUpgradeOpen(true)}
          style={{ cursor: "pointer" }}
          className="inline-flex items-center gap-1.5 rounded-md border border-indigo-300 px-3 py-1.5 text-xs font-medium text-indigo-700 hover:bg-indigo-50"
          data-testid="report-upgrade-trigger"
        >
          <ArrowUpCircle className="h-3.5 w-3.5" /> Upgrade Tier
        </button>
        <button
          type="button"
          onClick={() => setDisputeOpen(true)}
          style={{ cursor: "pointer" }}
          className="inline-flex items-center gap-1.5 rounded-md border border-red-300 px-3 py-1.5 text-xs font-medium text-red-700 hover:bg-red-50"
          data-testid="report-dispute-trigger"
        >
          <Flag className="h-3.5 w-3.5" /> File Dispute
        </button>
      </div>

      <ReportHeader
        vid={report.vid}
        version={report.version}
        tier={report.tier}
        completedAt={report.completedAt}
        trustScore={report.trustScore}
        onDownloadPdf={handleDownloadPdf}
        pdfLoading={pdfLoading}
      />

      {report.executiveSummary && (
        <div className="rounded-lg border border-indigo-100 bg-indigo-50 p-5">
          <h2 className="text-sm font-semibold text-indigo-800 mb-1">Executive Summary</h2>
          <p className="text-sm text-indigo-700">{report.executiveSummary}</p>
        </div>
      )}

      <ReportSection title="Registry Findings" defaultOpen>
        {renderKv(report.registryFindings)}
      </ReportSection>

      {report.physicalFindings !== null && (
        <ReportSection title="Physical Inspection">
          {renderKv(report.physicalFindings)}
        </ReportSection>
      )}

      {report.boundaryFindings !== null && (
        <ReportSection title="Boundary Survey">
          {renderKv(report.boundaryFindings)}
        </ReportSection>
      )}

      {report.legalOpinion !== null && (
        <ReportSection title="Legal Opinion">
          {renderKv(report.legalOpinion)}
        </ReportSection>
      )}

      {report.riskSummary && (
        <div className="rounded-lg border border-amber-100 bg-amber-50 p-5">
          <h2 className="text-sm font-semibold text-amber-800 mb-1">Risk Summary</h2>
          <p className="text-sm text-amber-700">{report.riskSummary}</p>
        </div>
      )}

      <ReportLegalFooter />
    </div>
  );
}
