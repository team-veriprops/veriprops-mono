import Link from "next/link";
import AdminConfigPanel from "@components/admin/config/AdminConfigPanel";
import type { Metadata } from "next";
import { ROUTES } from "@lib/routes";

export const metadata: Metadata = {
  title: "System Config | Veriprops Admin",
};

export default function AdminConfigPage() {
  return (
    <div className="p-6 space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-gray-900">System Configuration</h1>
        <p className="text-sm text-gray-500">Tune no-show timeouts, pool timeouts, and auto-assignment behaviour.</p>
      </div>
      <div className="rounded-lg border border-indigo-100 bg-indigo-50 p-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-semibold text-indigo-900">Trust Score Weights</p>
            <p className="text-xs text-indigo-600 mt-0.5">Configure per-tier, per-role weights for trust score computation.</p>
          </div>
          <Link
            href={ROUTES.ADMIN.TRUST_SCORE_WEIGHTS}
            className="rounded bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700"
          >
            Manage
          </Link>
        </div>
      </div>
      <AdminConfigPanel />
    </div>
  );
}
