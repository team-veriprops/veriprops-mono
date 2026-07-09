import { Suspense } from "react";
import AdminTeamManagement from "@components/admin/team/AdminTeamManagement";

export default function AdminTeamPage() {
  return (
    <div className="p-4 sm:p-6">
      <Suspense>
        <AdminTeamManagement />
      </Suspense>
    </div>
  );
}
