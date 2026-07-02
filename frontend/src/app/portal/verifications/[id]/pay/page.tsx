import PayContainer from "@components/portal/submission/PayContainer";

export default async function PayPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <PayContainer verificationId={id} />;
}
