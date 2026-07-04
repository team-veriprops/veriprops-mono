import ReportContainer from "@components/portal/verifications/ReportContainer";

export default async function VerificationReportPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ReportContainer verificationId={id} />;
}
