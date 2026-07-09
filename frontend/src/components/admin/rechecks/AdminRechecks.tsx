"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@3rdparty/ui/button";
import { Input } from "@3rdparty/ui/input";
import { Label } from "@3rdparty/ui/label";
import { AsyncStateComponent } from "@components/ui/AsyncStateComponent";
import DetailDrawer from "@components/ui/DetailDrawer";
import {
  useDecideRecheckMutation,
  usePendingRechecksQuery,
} from "@components/portal/libs/useRevisionQueries";
import { AgentRole } from "@/types/agent";
import { Recheck } from "@/types/revision";
import { Page } from "@/types/models";

/**
 * Admin re-check queue (§14.1): approve (scoping which roles to redo) or reject a pending
 * request. On approval the customer is charged the re-check fee before the cycle starts.
 */
export default function AdminRechecks() {
  const { data, isLoading, isError } = usePendingRechecksQuery();
  const [selected, setSelected] = useState<Recheck | null>(null);

  return (
    <div className="p-4 sm:p-6">
      <h1 className="mb-4 text-lg font-semibold">Pending re-checks</h1>
      <AsyncStateComponent<Page<Recheck>>
        isLoading={isLoading}
        isError={isError}
        data={data}
        loadingText="Loading re-checks…"
        emptyText="No pending re-checks."
      >
        {(page) => (
          <div className="space-y-2">
            {page.items.length === 0 && <p className="text-sm text-muted-foreground">No pending re-checks.</p>}
            {page.items.map((r) => (
              <button
                key={r.id}
                onClick={() => setSelected(r)}
                className="flex w-full items-center justify-between rounded-lg border p-3 text-left hover:bg-muted/50"
                data-testid="recheck-row"
              >
                <p className="truncate text-sm">{r.reason}</p>
                <span className="text-xs text-muted-foreground">₦{(r.priceMinor / 100).toLocaleString()}</span>
              </button>
            ))}
          </div>
        )}
      </AsyncStateComponent>

      <DetailDrawer
        open={!!selected}
        onOpenChange={(o) => !o && setSelected(null)}
        title="Review re-check"
        reference={selected?.id ?? ""}
      >
        {selected && <DecidePanel recheck={selected} onDone={() => setSelected(null)} />}
      </DetailDrawer>
    </div>
  );
}

function DecidePanel({ recheck, onDone }: { recheck: Recheck; onDone: () => void }) {
  const [roles, setRoles] = useState<AgentRole[]>([]);
  const [note, setNote] = useState("");
  const decide = useDecideRecheckMutation();

  const toggleRole = (r: AgentRole) =>
    setRoles((cur) => (cur.includes(r) ? cur.filter((x) => x !== r) : [...cur, r]));

  const run = (approve: boolean) => {
    if (approve && roles.length === 0) {
      toast.error("Select at least one role to re-check.");
      return;
    }
    decide.mutate(
      { recheckId: recheck.id, req: { approve, scopeRoles: approve ? roles : undefined, note: note || undefined } },
      {
        onSuccess: () => {
          toast.success(approve ? "Re-check approved" : "Re-check rejected");
          onDone();
        },
        onError: () => toast.error("Could not update the re-check."),
      },
    );
  };

  return (
    <div className="space-y-4 p-4">
      <section className="rounded-lg border p-3 text-sm">
        <p className="font-medium">Customer&apos;s reason</p>
        <p className="mt-1 whitespace-pre-line text-muted-foreground">{recheck.reason}</p>
      </section>

      <div className="space-y-2">
        <Label>Roles to re-check</Label>
        <div className="flex flex-wrap gap-2">
          {Object.values(AgentRole).map((r) => (
            <label key={r} className="flex items-center gap-1 text-sm">
              <input type="checkbox" checked={roles.includes(r)} onChange={() => toggleRole(r)} data-testid={`recheck-role-${r}`} />
              {r}
            </label>
          ))}
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="recheck-note">Note (optional)</Label>
        <Input id="recheck-note" value={note} onChange={(e) => setNote(e.target.value)} />
      </div>

      <div className="flex gap-2">
        <Button className="flex-1" onClick={() => run(true)} disabled={decide.isPending} data-testid="recheck-approve">
          Approve
        </Button>
        <Button className="flex-1" variant="outline" onClick={() => run(false)} disabled={decide.isPending} data-testid="recheck-reject">
          Reject
        </Button>
      </div>
    </div>
  );
}
