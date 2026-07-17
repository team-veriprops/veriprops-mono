import { Suspense } from "react";
import AdminUsersManagement from "@components/admin/users/AdminUsersManagement";

export default function AdminUsersPage() {
  return (
    <div className="p-4 sm:p-6">
      <Suspense>
        <AdminUsersManagement />
      </Suspense>
    </div>
  );
}
