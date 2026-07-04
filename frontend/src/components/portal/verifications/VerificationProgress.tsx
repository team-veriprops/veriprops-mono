import { Check, Clock, Lock } from "lucide-react";
import { Progress } from "@3rdparty/ui/progress";
import { cn } from "@lib/utils";
import { TrackingTask } from "@/types/tracking";

// Human role labels for the progress steps (§9.1 tier-adaptive steps).
const ROLE_STEP_LABEL: Record<string, string> = {
  REGISTRY: "Registry & Title",
  FIELD: "Physical Inspection",
  SURVEYOR: "Boundary & Survey",
  LAWYER: "Legal Opinion",
};

interface Props {
  tasks: TrackingTask[];
  progressPercent: number;
  className?: string;
}

/**
 * Portable customer progress tracker (§9.1/§9.3). Reused on the tracking detail and
 * the verifications list. Renders tier-adaptive steps with the collapsed customer-facing
 * state label; a dependency-blocked Lawyer row reads "Awaiting other stages".
 */
export function VerificationProgress({ tasks, progressPercent, className }: Props) {
  return (
    <div className={cn("space-y-4", className)}>
      <Progress value={progressPercent} aria-label="Verification progress" />
      <ol className="space-y-2">
        {tasks.map((task) => (
          <li key={task.role} className="flex items-center gap-3 text-sm">
            <StepIcon completed={task.completed} locked={task.locked} />
            <span className="flex-1 font-medium">{ROLE_STEP_LABEL[task.role] ?? task.role}</span>
            <span className={cn("text-xs", task.locked ? "text-muted-foreground" : "text-foreground")}>
              {task.stateLabel}
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}

function StepIcon({ completed, locked }: { completed: boolean; locked: boolean }) {
  if (completed) {
    return (
      <span className="flex size-6 items-center justify-center rounded-full bg-primary text-primary-foreground">
        <Check className="size-3.5" />
      </span>
    );
  }
  if (locked) {
    return (
      <span className="flex size-6 items-center justify-center rounded-full bg-muted text-muted-foreground">
        <Lock className="size-3.5" />
      </span>
    );
  }
  return (
    <span className="flex size-6 items-center justify-center rounded-full border text-muted-foreground">
      <Clock className="size-3.5" />
    </span>
  );
}
