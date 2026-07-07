import { Suspense } from "react";
import AdminAuditLog from "@components/admin/audit/AdminAuditLog";

export default function AdminAuditLogPage() {
  return (
    <div className="p-4 sm:p-6">
      <Suspense>
        <AdminAuditLog />
      </Suspense>
    </div>
  );
}
