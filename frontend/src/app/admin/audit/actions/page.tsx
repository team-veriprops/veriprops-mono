import { Suspense } from "react";
import AdminAuditLog from "@components/admin/audit/AdminAuditLog";

export default function AdminAuditLogPage() {
  return (
    <Suspense>
      <AdminAuditLog />
    </Suspense>
  );
}
