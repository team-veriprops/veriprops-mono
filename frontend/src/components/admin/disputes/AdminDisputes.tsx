"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@3rdparty/ui/button";
import { Textarea } from "@3rdparty/ui/textarea";
import { Label } from "@3rdparty/ui/label";
import { AsyncStateComponent } from "@components/ui/AsyncStateComponent";
import DetailDrawer from "@components/ui/DetailDrawer";
import { humanizeEnumLabel } from "@lib/utils";
import {
  useOpenDisputesQuery,
  useResolveDisputeMutation,
} from "@components/portal/libs/useRevisionQueries";
import { AgentRole } from "@/types/agent";
import { Dispute, DisputeOutcome, ResolveDisputeRequest } from "@/types/revision";
import { Page } from "@/types/models";

const OUTCOME_LABEL: Record<DisputeOutcome, string> = {
  [DisputeOutcome.REJECTED]: "Reject — back to Completed",
  [DisputeOutcome.FULL_REFUND]: "Uphold — full refund",
  [DisputeOutcome.PARTIAL_RECHECK]: "Uphold — free re-check",
};

/**
 * Admin dispute queue + resolution (§14.3). Each dispute shows the customer's complaint and the
 * agent's defence (if any); the admin resolves with one of the three outcomes + a mandatory note
 * delivered verbatim to the customer.
 */
export default function AdminDisputes() {
  const { data, isLoading, isError } = useOpenDisputesQuery();
  const [selected, setSelected] = useState<Dispute | null>(null);

  return (
    <div className="p-4 sm:p-6">
      <h1 className="mb-4 text-lg font-semibold">Open disputes</h1>
      <AsyncStateComponent<Page<Dispute>>
        isLoading={isLoading}
        isError={isError}
        data={data}
        loadingText="Loading disputes…"
        emptyText="No open disputes."
      >
        {(page) => (
          <div className="space-y-2">
            {page.items.length === 0 && <p className="text-sm text-muted-foreground">No open disputes.</p>}
            {page.items.map((d) => (
              <button
                key={d.id}
                onClick={() => setSelected(d)}
                className="flex w-full items-center justify-between rounded-lg border p-3 text-left hover:bg-muted/50"
                data-testid="dispute-row"
              >
                <div className="min-w-0">
                  <p className="text-sm font-medium">{humanizeEnumLabel(d.disputeType)}</p>
                  <p className="truncate text-xs text-muted-foreground">{d.description}</p>
                </div>
                <span className="text-xs text-muted-foreground">{new Date(d.dateCreated).toLocaleDateString()}</span>
              </button>
            ))}
          </div>
        )}
      </AsyncStateComponent>

      <DetailDrawer
        open={!!selected}
        onOpenChange={(o) => !o && setSelected(null)}
        title="Resolve dispute"
        reference={selected?.id ?? ""}
      >
        {selected && <ResolvePanel dispute={selected} onDone={() => setSelected(null)} />}
      </DetailDrawer>
    </div>
  );
}

function ResolvePanel({ dispute, onDone }: { dispute: Dispute; onDone: () => void }) {
  const [outcome, setOutcome] = useState<DisputeOutcome>(DisputeOutcome.REJECTED);
  const [note, setNote] = useState("");
  const [roles, setRoles] = useState<AgentRole[]>(dispute.targetRole ? [dispute.targetRole] : []);
  const resolve = useResolveDisputeMutation();

  const submit = () => {
    if (!note.trim()) {
      toast.error("A resolution note is required — it's delivered to the customer.");
      return;
    }
    const req: ResolveDisputeRequest = { outcome, note: note.trim() };
    if (outcome === DisputeOutcome.PARTIAL_RECHECK) {
      if (roles.length === 0) {
        toast.error("Select at least one role for the free re-check.");
        return;
      }
      req.scopeRoles = roles;
    }
    resolve.mutate(
      { disputeId: dispute.id, req },
      {
        onSuccess: () => {
          toast.success("Dispute resolved");
          onDone();
        },
        onError: () => toast.error("Could not resolve the dispute."),
      },
    );
  };

  const toggleRole = (r: AgentRole) =>
    setRoles((cur) => (cur.includes(r) ? cur.filter((x) => x !== r) : [...cur, r]));

  return (
    <div className="space-y-4 p-4">
      <section className="rounded-lg border p-3 text-sm">
        <p className="font-medium">Customer&apos;s complaint</p>
        <p className="mt-1 whitespace-pre-line text-muted-foreground">{dispute.description}</p>
      </section>
      {dispute.agentDefenceText && (
        <section className="rounded-lg border border-blue-200 bg-blue-50 p-3 text-sm">
          <p className="font-medium">Agent&apos;s defence</p>
          <p className="mt-1 whitespace-pre-line text-muted-foreground">{dispute.agentDefenceText}</p>
        </section>
      )}

      <div className="space-y-2">
        <Label>Outcome</Label>
        <div className="space-y-1">
          {Object.values(DisputeOutcome).map((o) => (
            <label key={o} className="flex items-center gap-2 text-sm">
              <input
                type="radio"
                name="outcome"
                checked={outcome === o}
                onChange={() => setOutcome(o)}
                data-testid={`outcome-${o}`}
              />
              {OUTCOME_LABEL[o]}
            </label>
          ))}
        </div>
      </div>

      {outcome === DisputeOutcome.PARTIAL_RECHECK && (
        <div className="space-y-2">
          <Label>Roles to re-check (free)</Label>
          <div className="flex flex-wrap gap-2">
            {Object.values(AgentRole).map((r) => (
              <label key={r} className="flex items-center gap-1 text-sm">
                <input type="checkbox" checked={roles.includes(r)} onChange={() => toggleRole(r)} />
                {r}
              </label>
            ))}
          </div>
        </div>
      )}

      <div className="space-y-2">
        <Label htmlFor="resolve-note">Resolution note (sent to the customer)</Label>
        <Textarea
          id="resolve-note"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          rows={4}
          data-testid="resolve-note"
        />
      </div>

      <Button className="w-full" onClick={submit} disabled={resolve.isPending} data-testid="resolve-submit">
        {resolve.isPending ? "Resolving…" : "Resolve dispute"}
      </Button>
    </div>
  );
}
