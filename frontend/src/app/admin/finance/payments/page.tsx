import type { Metadata } from "next";
import PaymentsTable from "@components/admin/finance/PaymentsTable";

export const metadata: Metadata = {
  title: "Payments | Veriprops Admin",
};

export default function PaymentsPage() {
  return (
    <div className="p-6 lg:p-8 max-w-6xl mx-auto">
      <PaymentsTable />
    </div>
  );
}
