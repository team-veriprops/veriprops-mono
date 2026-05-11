import AdminConfigPanel from "@components/admin/config/AdminConfigPanel";
import type { Metadata } from "next";

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
      <AdminConfigPanel />
    </div>
  );
}
