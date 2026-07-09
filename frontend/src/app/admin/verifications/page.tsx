import { Suspense } from "react";
import AdminVerificationList from "@components/admin/verifications/AdminVerificationList";

export default function AdminVerificationsPage() {
  return (
    <div className="p-4 sm:p-6">
      <Suspense>
        <AdminVerificationList />
      </Suspense>
    </div>
  );
}
