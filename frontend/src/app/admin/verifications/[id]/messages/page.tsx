import AdminMessagesContainer from "@components/chat/AdminMessagesContainer";

export default async function AdminVerificationMessagesPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <div className="p-6">
      <AdminMessagesContainer verificationId={id} />
    </div>
  );
}
