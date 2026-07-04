import EvidenceContainer from "@components/portal/verifications/EvidenceContainer";

export default async function VerificationEvidencePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <EvidenceContainer verificationId={id} />;
}
