import AgentMessagesContainer from "@components/chat/AgentMessagesContainer";

export default async function AgentTaskMessagesPage({
  params,
}: {
  params: Promise<{ taskId: string }>;
}) {
  const { taskId } = await params;
  return (
    <div className="p-6">
      <AgentMessagesContainer taskId={taskId} />
    </div>
  );
}
