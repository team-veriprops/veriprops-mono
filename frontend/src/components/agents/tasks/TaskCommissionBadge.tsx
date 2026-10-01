import { Banknote } from "lucide-react";
import { Badge } from "@3rdparty/ui/badge";
import ToolTipComponent from "@components/ui/ToolTipComponent";
import { formatMinor } from "@lib/utils";
import { AgentTask } from "@/types/agentTask";

/**
 * What a task pays the agent, shown on the task card and the task page so it is visible before
 * they accept (§12.1 / §20.1): the role's fixed commission — the same on every tier — and, when
 * the task carries one, its remote bonus, which is paid as its own ledger line. Both figures are
 * the backend's, rendered as given; nothing here derives, adds or scales them.
 */
export function TaskCommissionBadge({
  task,
}: {
  task: Pick<AgentTask, "id" | "commissionMinor" | "remoteBonusMinor">;
}) {
  return (
    <>
      <ToolTipComponent label="Your fixed pay for this role, earned when the task is approved.">
        <Badge variant="outline" className="gap-1 tabular-nums" data-testid={`task-commission-${task.id}`}>
          <Banknote className="size-3" aria-hidden />
          <span className="sr-only">Pays </span>
          {formatMinor(task.commissionMinor)}
        </Badge>
      </ToolTipComponent>
      {task.remoteBonusMinor ? (
        <ToolTipComponent label="Extra pay this job carries because it waited in the open pool; paid with the task.">
          <Badge
            variant="outline"
            className="gap-1 tabular-nums text-emerald-700 dark:text-emerald-400"
            data-testid={`task-bonus-${task.id}`}
          >
            + {formatMinor(task.remoteBonusMinor)} remote bonus
          </Badge>
        </ToolTipComponent>
      ) : null}
    </>
  );
}
