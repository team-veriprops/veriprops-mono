"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, ImageIcon, Sparkles } from "lucide-react";
import { Badge } from "@3rdparty/ui/badge";
import { Button } from "@3rdparty/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@3rdparty/ui/select";
import { AsyncStateComponent } from "@components/ui/AsyncStateComponent";
import { StatusPill } from "@components/ui/StatusPill";
import { toast } from "@components/3rdparty/ui/use-toast";
import { ROUTES } from "@/lib/routes";
import { TaskState } from "@/types/adminVerification";
import { AgentTask } from "@/types/agentTask";
import { Page } from "@/types/models";
import { humanizeEnumLabel } from "@lib/utils";
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
  const [page, setPage] = useState(0);
  const { data, isLoading, isError } = useAgentTasksQuery(stateFilter, page, PAGE_SIZE);
  const accept = useAcceptTaskMutation();
  const decline = useDeclineTaskMutation();

  const onFilterChange = (v: string) => {
    setStateFilter(v === ALL ? undefined : v);
    setPage(0); // a new filter resets to the first page
  };

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-4 sm:p-6" data-testid="agent-tasks">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-lg font-semibold text-foreground">My tasks</h1>
          <p className="text-sm text-muted-foreground">
            Accept assignments, capture evidence on-site, and submit your findings.
          </p>
        </div>
        <Select value={stateFilter ?? ALL} onValueChange={onFilterChange}>
          <SelectTrigger className="w-44" data-testid="agent-task-state-filter">
            <SelectValue placeholder="State" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All states</SelectItem>
            {Object.values(TaskState).map((s) => (
              <SelectItem key={s} value={s}>
                {humanizeEnumLabel(s)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <AsyncStateComponent<Page<AgentTask>>
        isLoading={isLoading}
        isError={isError}
        data={data}
        loadingText="Loading tasks…"
        emptyText="No tasks yet."
      >
        {(pageData) =>
          pageData.items.length === 0 ? (
            <div className="rounded-xl border border-dashed border-border py-16 text-center">
              <p className="text-sm text-muted-foreground">
                {stateFilter ? "No tasks in this state." : "No tasks assigned yet — check back soon."}
              </p>
            </div>
          ) : (
            <>
              <div className="grid gap-3">
                {pageData.items.map((task) => {
                  const canAccept = task.state === TaskState.PENDING || task.inPool;
                  const canDecline =
                    task.state === TaskState.ASSIGNED || task.state === TaskState.ACCEPTED;
                  return (
                    <div
                      key={task.id}
                      className="rounded-xl border border-border p-4 transition-colors hover:border-primary/40"
                      data-testid={`agent-task-${task.id}`}
                    >
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="min-w-0 space-y-1.5">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="font-semibold text-foreground">
                              {humanizeEnumLabel(task.role)}
                            </span>
                            <StatusPill status={task.state} />
                            <Badge variant="secondary">{humanizeEnumLabel(task.tier)}</Badge>
                            {task.inPool && (
                              <Badge className="gap-1">
                                <Sparkles className="size-3" /> Open pool
                              </Badge>
                            )}
                          </div>
                          <p className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-sm text-muted-foreground">
                            <span>Verification {task.verificationId.slice(0, 8)}</span>
                            <span aria-hidden>·</span>
                            <span className="inline-flex items-center gap-1">
                              <ImageIcon className="size-3.5" /> {task.evidenceCount} evidence
                            </span>
                            {task.remoteBonusMinor ? (
                              <>
                                <span aria-hidden>·</span>
                                <span className="text-emerald-600 dark:text-emerald-400">remote bonus</span>
                              </>
                            ) : null}
                          </p>
                        </div>
                        <div className="flex shrink-0 gap-2">
                          {canAccept && (
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
                          {canDecline && (
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
                            className="gap-1"
                            onClick={() => router.push(ROUTES.AGENT.TASK_DETAIL(task.id))}
                          >
                            Open <ArrowRight className="size-3.5" />
                          </Button>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>

              {(page > 0 || pageData.meta.nextPage != null) && (
                <div className="flex items-center justify-between pt-1">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page === 0}
                    onClick={() => setPage((p) => Math.max(0, p - 1))}
                  >
                    Previous
                  </Button>
                  <span className="text-xs text-muted-foreground">
                    Page {page + 1} of {Math.max(pageData.meta.totalPages, 1)}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={pageData.meta.nextPage == null}
                    onClick={() => setPage((p) => p + 1)}
                  >
                    Next
                  </Button>
                </div>
              )}
            </>
          )
        }
      </AsyncStateComponent>
    </div>
  );
}
