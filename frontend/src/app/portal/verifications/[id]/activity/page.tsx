import VerificationActivity from "@components/portal/verifications/VerificationActivity";

export default async function VerificationActivityPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <VerificationActivity verificationId={id} />;
}
