import TaskHistory from "@components/agents/tasks/TaskHistory";

export default async function TaskHistoryPage({
  params,
}: {
  params: Promise<{ taskId: string }>;
}) {
  const { taskId } = await params;
  return <TaskHistory taskId={taskId} />;
}
