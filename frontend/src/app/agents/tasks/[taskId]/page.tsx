import AgentTaskDetail from "@components/agents/tasks/AgentTaskDetail";
import DrawerRoutePage from "@components/ui/DrawerRoutePage";
import { ROUTES } from "@lib/routes";

export default async function AgentTaskDetailPage({
  params,
}: {
  params: Promise<{ taskId: string }>;
}) {
  const { taskId } = await params;
  return (
    <DrawerRoutePage title="Task" reference={taskId} fallbackHref={ROUTES.AGENT.TASKS}>
      <div className="p-6">
        <AgentTaskDetail taskId={taskId} />
      </div>
    </DrawerRoutePage>
  );
}
