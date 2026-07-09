import { Check, Clock, Lock } from "lucide-react";
import { Progress } from "@3rdparty/ui/progress";
import { cn, humanizeEnumLabel } from "@lib/utils";
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
 * the verifications list. Renders tier-adaptive steps as a connected timeline with the
 * collapsed customer-facing state label; a dependency-blocked Lawyer row reads
 * "Awaiting other stages".
 */
export function VerificationProgress({ tasks, progressPercent, className }: Props) {
  return (
    <div className={cn("space-y-4", className)}>
      <Progress value={progressPercent} aria-label="Verification progress" />
      <ol className="relative">
        {tasks.map((task, i) => {
          const active = !task.completed && !task.locked;
          return (
            <li key={task.role} className="relative flex gap-3 pb-5 last:pb-0">
              {/* Timeline rail connecting this node to the next. */}
              {i < tasks.length - 1 && (
                <span
                  aria-hidden
                  className={cn(
                    "absolute left-3 top-7 h-full w-px -translate-x-1/2",
                    task.completed ? "bg-primary" : "bg-border",
                  )}
                />
              )}
              <StepIcon completed={task.completed} locked={task.locked} active={active} />
              <div className="flex flex-1 items-center justify-between gap-2 pt-0.5">
                <span className={cn("text-sm font-medium", task.locked && "text-muted-foreground")}>
                  {ROLE_STEP_LABEL[task.role] ?? humanizeEnumLabel(task.role)}
                </span>
                <span
                  className={cn(
                    "text-xs",
                    active ? "font-medium text-primary" : task.locked ? "text-muted-foreground" : "text-foreground",
                  )}
                >
                  {task.stateLabel}
                </span>
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function StepIcon({ completed, locked, active }: { completed: boolean; locked: boolean; active: boolean }) {
  if (completed) {
    return (
      <span className="relative z-10 flex size-6 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground">
        <Check className="size-3.5" />
      </span>
    );
  }
  if (locked) {
    return (
      <span className="relative z-10 flex size-6 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground">
        <Lock className="size-3.5" />
      </span>
    );
  }
  // In-progress: a pulsing ring draws the eye to "where we are now".
  return (
    <span className="relative z-10 flex size-6 shrink-0 items-center justify-center rounded-full border border-primary bg-background text-primary">
      {active && <span className="absolute inline-flex size-6 animate-ping rounded-full bg-primary/20" />}
      <Clock className="size-3.5" />
    </span>
  );
}
