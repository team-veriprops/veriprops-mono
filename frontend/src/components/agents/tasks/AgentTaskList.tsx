"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Badge } from "@3rdparty/ui/badge";
import { Button } from "@3rdparty/ui/button";
import { Card, CardContent } from "@3rdparty/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@3rdparty/ui/select";
import { toast } from "@components/3rdparty/ui/use-toast";
import { Loader2 } from "lucide-react";
import { ROUTES } from "@/lib/routes";
import { TaskState } from "@/types/adminVerification";
import { AgentTask } from "@/types/agentTask";
import {
  useAcceptTaskMutation,
  useAgentTasksQuery,
  useDeclineTaskMutation,
} from "./libs/useAgentTaskQueries";

const ALL = "ALL";
const PAGE_SIZE = 10;

export default function AgentTaskList() {
  const router = useRouter();
  const [stateFilter, setStateFilter] = useState<string | undefined>();
  const { data, isLoading } = useAgentTasksQuery(stateFilter, 0, PAGE_SIZE);
  const accept = useAcceptTaskMutation();
  const decline = useDeclineTaskMutation();

  const tasks = data?.items ?? [];

  return (
    <div className="space-y-6" data-testid="agent-tasks">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-2xl font-bold text-foreground">My tasks</h1>
        <Select
          value={stateFilter ?? ALL}
          onValueChange={(v) => setStateFilter(v === ALL ? undefined : v)}
        >
          <SelectTrigger className="w-44" data-testid="agent-task-state-filter">
            <SelectValue placeholder="State" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All states</SelectItem>
            {Object.values(TaskState).map((s) => (
              <SelectItem key={s} value={s}>
                {s}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-16 text-muted-foreground">
          <Loader2 className="mr-2 h-5 w-5 animate-spin" /> Loading tasks…
        </div>
      ) : tasks.length === 0 ? (
        <p className="py-16 text-center text-muted-foreground">No tasks yet.</p>
      ) : (
        <div className="grid gap-3">
          {tasks.map((task: AgentTask) => (
            <Card key={task.id} data-testid={`agent-task-${task.id}`}>
              <CardContent className="flex flex-wrap items-center justify-between gap-3 p-4">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{task.role}</span>
                    <Badge variant="outline">{task.state}</Badge>
                    <Badge variant="secondary">{task.tier}</Badge>
                    {task.inPool && <Badge>Open pool</Badge>}
                  </div>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Verification {task.verificationId.slice(0, 8)} · {task.evidenceCount} evidence
                    {task.remoteBonusMinor ? " · remote bonus" : ""}
                  </p>
                </div>
                <div className="flex gap-2">
                  {(task.state === TaskState.PENDING || task.inPool) && (
                    <Button
                      size="sm"
                      onClick={async () => {
                        await accept.mutateAsync(task.id);
                        toast({ title: "Task accepted" });
                      }}
                      disabled={accept.isPending}
                      data-testid={`accept-${task.id}`}
                    >
                      Accept
                    </Button>
                  )}
                  {(task.state === TaskState.ASSIGNED || task.state === TaskState.ACCEPTED) && (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={async () => {
                        await decline.mutateAsync({ taskId: task.id });
                        toast({ title: "Task declined" });
                      }}
                      disabled={decline.isPending}
                      data-testid={`decline-${task.id}`}
                    >
                      Decline
                    </Button>
                  )}
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => router.push(ROUTES.AGENT.TASK_DETAIL(task.id))}
                  >
                    Open
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
