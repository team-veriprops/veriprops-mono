import TrackingContainer from "@components/portal/verifications/TrackingContainer";

export default async function VerificationTrackingPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <TrackingContainer verificationId={id} />;
}
