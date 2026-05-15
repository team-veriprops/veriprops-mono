import VerificationDetail from "@components/admin/verifications/VerificationDetail";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Verification Detail | Veriprops Admin",
};

interface Props {
  params: Promise<{ vid: string }>;
}

export default async function AdminVerificationDetailPage({ params }: Props) {
  
  const { vid } = await params;

  return (
    <div className="p-6">
      <VerificationDetail vid={vid} />
    </div>
  );
}
