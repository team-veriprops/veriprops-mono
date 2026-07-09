import { Suspense } from "react";
import AdminErasureRequests from "@components/admin/erasure/AdminErasureRequests";

export default function AdminErasureRequestsPage() {
  return (
    <Suspense>
      <AdminErasureRequests />
    </Suspense>
  );
}
