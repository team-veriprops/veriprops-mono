import VerificationQueue from "@components/admin/verifications/VerificationQueue";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Verifications | Veriprops Admin",
};

export default function AdminVerificationsPage() {
  return (
    <div className="p-6 space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-gray-900">Verifications</h1>
        <p className="text-sm text-gray-500">Manage and review all property verification requests.</p>
      </div>
      <VerificationQueue />
    </div>
  );
}
