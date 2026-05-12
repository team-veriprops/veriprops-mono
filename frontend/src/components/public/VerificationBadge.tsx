import { CheckCircle, Clock, AlertTriangle } from "lucide-react";

interface Props {
  status: string;
  trustBand?: "HIGH" | "MED" | "LOW";
}

const BAND_STYLES = {
  HIGH: "bg-green-100 text-green-800 border-green-200",
  MED: "bg-yellow-100 text-yellow-800 border-yellow-200",
  LOW: "bg-red-100 text-red-800 border-red-200",
};

export default function VerificationBadge({ status, trustBand }: Props) {
  if (status === "COMPLETED" && trustBand) {
    return (
      <div
        className={`inline-flex items-center gap-2 rounded-full border px-4 py-2 font-semibold text-sm ${BAND_STYLES[trustBand]}`}
        data-testid="verification-badge"
      >
        <CheckCircle className="h-4 w-4" />
        Verified · {trustBand} Trust
      </div>
    );
  }
  if (status === "IN_PROGRESS") {
    return (
      <div
        className="inline-flex items-center gap-2 rounded-full border border-blue-200 bg-blue-50 px-4 py-2 text-sm font-semibold text-blue-800"
        data-testid="verification-badge"
      >
        <Clock className="h-4 w-4" />
        Verification In Progress
      </div>
    );
  }
  return (
    <div
      className="inline-flex items-center gap-2 rounded-full border border-orange-200 bg-orange-50 px-4 py-2 text-sm font-semibold text-orange-800"
      data-testid="verification-badge"
    >
      <AlertTriangle className="h-4 w-4" />
      Under Review
    </div>
  );
}
