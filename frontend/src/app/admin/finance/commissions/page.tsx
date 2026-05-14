import type { Metadata } from "next";
import CommissionBreakdownTable from "@components/admin/finance/CommissionBreakdownTable";

export const metadata: Metadata = {
  title: "Commissions | Veriprops Admin",
};

export default function CommissionsPage() {
  return (
    <div className="p-6 lg:p-8 max-w-6xl mx-auto">
      <CommissionBreakdownTable />
    </div>
  );
}
