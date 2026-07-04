import AgentTaskDetail from "@components/agents/tasks/AgentTaskDetail";

export default async function AgentTaskDetailPage({
  params,
}: {
  params: Promise<{ taskId: string }>;
}) {
  const { taskId } = await params;
  return (
    <div className="p-4 sm:p-6">
      <AgentTaskDetail taskId={taskId} />
    </div>
  );
}
