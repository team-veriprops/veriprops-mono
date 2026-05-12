import { PublicVerificationSummary } from "./models";

interface Props {
  summary: PublicVerificationSummary;
}

export default function PublicSummaryCard({ summary }: Props) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm" data-testid="public-summary-card">
      <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3">
        <div>
          <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">Verification ID</dt>
          <dd className="mt-1 text-sm font-mono font-semibold text-gray-900">{summary.vid}</dd>
        </div>
        <div>
          <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">Tier</dt>
          <dd className="mt-1 text-sm font-semibold text-gray-900">{summary.tier}</dd>
        </div>
        <div>
          <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">Property Type</dt>
          <dd className="mt-1 text-sm text-gray-900">{summary.propertyType}</dd>
        </div>
        <div>
          <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">State</dt>
          <dd className="mt-1 text-sm text-gray-900">{summary.state}</dd>
        </div>
        <div>
          <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">LGA</dt>
          <dd className="mt-1 text-sm text-gray-900">{summary.lga}</dd>
        </div>
        {summary.reportDate && (
          <div>
            <dt className="text-xs font-medium uppercase tracking-wide text-gray-500">Report Date</dt>
            <dd className="mt-1 text-sm text-gray-900">
              {new Date(summary.reportDate).toLocaleDateString()}
            </dd>
          </div>
        )}
      </dl>
    </div>
  );
}
