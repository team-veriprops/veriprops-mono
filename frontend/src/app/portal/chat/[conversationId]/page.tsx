import CustomerConversationContainer from "@components/chat/CustomerConversationContainer";

export default async function ConversationPage({
  params,
}: {
  params: Promise<{ conversationId: string }>;
}) {
  const { conversationId } = await params;
  return (
    <div className="p-6">
      <CustomerConversationContainer conversationId={conversationId} />
    </div>
  );
}
