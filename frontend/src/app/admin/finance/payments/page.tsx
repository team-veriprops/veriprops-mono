import { Suspense } from "react";
import AdminPayments from "@components/admin/finance/AdminPayments";

export default function AdminPaymentsPage() {
  return (
    <Suspense>
      <AdminPayments />
    </Suspense>
  );
}
