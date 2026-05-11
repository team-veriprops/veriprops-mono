import VerificationDetail from "@components/admin/verifications/VerificationDetail";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Verification Detail | Veriprops Admin",
};

interface Props {
  params: { vid: string };
}

export default function AdminVerificationDetailPage({ params }: Props) {
  return (
    <div className="p-6">
      <VerificationDetail vid={params.vid} />
    </div>
  );
}
