import { Suspense } from "react";
import AdminErasureRequests from "@components/admin/erasure/AdminErasureRequests";

export default function AdminErasureRequestsPage() {
  return (
    <div className="p-4 sm:p-6">
      <Suspense>
        <AdminErasureRequests />
      </Suspense>
    </div>
  );
}
