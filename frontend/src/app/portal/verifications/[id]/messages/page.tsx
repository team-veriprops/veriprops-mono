import CustomerMessagesContainer from "@components/chat/CustomerMessagesContainer";

export default async function VerificationMessagesPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <div className="p-6">
      <CustomerMessagesContainer verificationId={id} />
    </div>
  );
}
