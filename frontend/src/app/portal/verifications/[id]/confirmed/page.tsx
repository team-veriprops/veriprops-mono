import ConfirmationContainer from "@components/portal/submission/ConfirmationContainer";

export default async function ConfirmedPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ConfirmationContainer verificationId={id} />;
}
