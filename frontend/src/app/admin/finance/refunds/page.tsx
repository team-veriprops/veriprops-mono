import { Suspense } from "react";
import RefundApprovals from "@components/admin/finance/RefundApprovals";

export default function RefundApprovalsPage() {
  return (
    <Suspense>
      <RefundApprovals />
    </Suspense>
  );
}
