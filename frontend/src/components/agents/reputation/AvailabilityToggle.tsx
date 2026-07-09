"use client";

import { toast } from "sonner";
import { cn } from "@lib/utils";
import { AvailabilityStatus } from "@/types/agentReputation";
import { useSetAvailabilityMutation } from "./libs/useReputationQueries";

const OPTIONS: { value: AvailabilityStatus; label: string; dot: string }[] = [
  { value: AvailabilityStatus.GREEN, label: "Available", dot: "bg-emerald-500" },
  { value: AvailabilityStatus.AMBER, label: "Limited", dot: "bg-amber-500" },
  { value: AvailabilityStatus.RED, label: "Unavailable", dot: "bg-red-500" },
];

/**
 * Agent availability control (§16.1). The effective status is forced to Unavailable at capacity
 * by the backend, so when ``atCapacity`` the control is read-only and shows the forced state.
 */
export function AvailabilityToggle({
  value,
  effective,
  atCapacity,
}: {
  value: AvailabilityStatus;
  effective: AvailabilityStatus;
  atCapacity: boolean;
}) {
  const set = useSetAvailabilityMutation();

  return (
    <div className="space-y-1">
      <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Availability">
        {OPTIONS.map((o) => {
          const active = value === o.value;
          return (
            <button
              key={o.value}
              role="radio"
              aria-checked={active}
              disabled={atCapacity || set.isPending}
              onClick={() =>
                set.mutate(o.value, { onError: () => toast.error("Could not update availability.") })
              }
              className={cn(
                "inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm transition",
                active ? "border-primary bg-primary/10" : "hover:bg-muted",
                atCapacity && "opacity-60",
              )}
              data-testid={`availability-${o.value}`}
            >
              <span className={cn("size-2.5 rounded-full", o.dot)} />
              {o.label}
            </button>
          );
        })}
      </div>
      {atCapacity && (
        <p className="text-xs text-amber-600 dark:text-amber-400">
          You&apos;re at your active-task limit, so you show as Unavailable ({effective}) until a task frees up.
        </p>
      )}
    </div>
  );
}
