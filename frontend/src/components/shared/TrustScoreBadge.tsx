"use client";

import { Info } from "lucide-react";

type Band = "EXCELLENT" | "GOOD" | "FAIR" | "POOR";

function getBand(score: number): Band {
  if (score >= 80) return "EXCELLENT";
  if (score >= 60) return "GOOD";
  if (score >= 40) return "FAIR";
  return "POOR";
}

const BAND_STYLES: Record<Band, string> = {
  EXCELLENT: "bg-green-100 text-green-800 border-green-200",
  GOOD: "bg-blue-100 text-blue-800 border-blue-200",
  FAIR: "bg-yellow-100 text-yellow-800 border-yellow-200",
  POOR: "bg-red-100 text-red-800 border-red-200",
};

const BAND_DESCRIPTIONS: Record<Band, string> = {
  EXCELLENT: "High confidence — findings are consistent across all agents.",
  GOOD: "Solid verification with minor discrepancies.",
  FAIR: "Some inconsistencies detected. Review recommended.",
  POOR: "Significant discrepancies. Escalation recommended.",
};

interface Props {
  score: number | null;
  size?: "sm" | "md" | "lg";
  showTooltip?: boolean;
}

export default function TrustScoreBadge({
  score,
  size = "md",
  showTooltip = true,
}: Props) {
  if (score === null || score === undefined) {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded border border-gray-200 bg-gray-50 text-gray-400 text-xs">
        No score yet
      </span>
    );
  }

  const band = getBand(score);
  const sizeClasses =
    size === "sm"
      ? "text-xs px-2 py-0.5"
      : size === "lg"
      ? "text-base px-3 py-1"
      : "text-sm px-2.5 py-0.5";

  return (
    <span
      className={`group relative inline-flex items-center gap-1.5 rounded-full border font-semibold ${sizeClasses} ${BAND_STYLES[band]}`}
      title={showTooltip ? BAND_DESCRIPTIONS[band] : undefined}
    >
      <span className="tabular-nums">{score.toFixed(1)}</span>
      <span className="opacity-70">/ 100</span>
      <span className="font-normal opacity-80">{band}</span>
      {showTooltip && <Info className="h-3 w-3 opacity-50" />}
    </span>
  );
}
