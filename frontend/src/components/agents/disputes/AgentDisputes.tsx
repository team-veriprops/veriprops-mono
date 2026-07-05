"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@3rdparty/ui/button";
import { Textarea } from "@3rdparty/ui/textarea";
import { AsyncStateComponent } from "@components/ui/AsyncStateComponent";
import {
  useAgentDisputesQuery,
  useSubmitDefenceMutation,
} from "@components/portal/libs/useRevisionQueries";
import { Dispute } from "@/types/revision";

/**
 * Agent dispute-defence (§14.3). Admin-mediated: the agent responds to a dispute touching their
 * task so the admin sees their account before resolving. The customer's identity is never shown.
 */
export default function AgentDisputes() {
  const { data, isLoading, isError } = useAgentDisputesQuery();

  return (
    <div className="mx-auto max-w-2xl p-4 sm:p-6">
      <h1 className="mb-1 text-lg font-semibold">Disputes awaiting your response</h1>
      <p className="mb-4 text-sm text-muted-foreground">
        Your account helps the admin resolve fairly. All communication is through Veriprops.
      </p>
      <AsyncStateComponent<Dispute[]>
        isLoading={isLoading}
        isError={isError}
        data={data}
        loadingText="Loading…"
        emptyText="No disputes need your response."
      >
        {(disputes) =>
          disputes.length === 0 ? (
            <p className="text-sm text-muted-foreground">No disputes need your response.</p>
          ) : (
            <div className="space-y-3">
              {disputes.map((d) => (
                <DefenceCard key={d.id} dispute={d} />
              ))}
            </div>
          )
        }
      </AsyncStateComponent>
    </div>
  );
}

function DefenceCard({ dispute }: { dispute: Dispute }) {
  const [text, setText] = useState(dispute.agentDefenceText ?? "");
  const submit = useSubmitDefenceMutation();
  const done = !!dispute.agentDefenceAt;

  const send = () => {
    if (!text.trim()) {
      toast.error("Please add your response.");
      return;
    }
    submit.mutate(
      { disputeId: dispute.id, text: text.trim() },
      {
        onSuccess: () => toast.success("Response sent to the admin."),
        onError: () => toast.error("Could not send your response. The window may have closed."),
      },
    );
  };

  return (
    <div className="space-y-3 rounded-lg border p-4" data-testid="agent-dispute-card">
      <div>
        <p className="text-sm font-medium">
          {dispute.disputeType.replace(/_/g, " ")}
          {dispute.targetRole ? ` · ${dispute.targetRole}` : ""}
        </p>
        <p className="mt-1 whitespace-pre-line text-sm text-muted-foreground">{dispute.description}</p>
      </div>
      <Textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={4}
        placeholder="Explain what you did and what you found…"
        disabled={done}
        data-testid="agent-defence-text"
      />
      {done ? (
        <p className="text-xs text-emerald-600">Your response has been recorded.</p>
      ) : (
        <Button onClick={send} disabled={submit.isPending} data-testid="agent-defence-submit">
          {submit.isPending ? "Sending…" : "Send response"}
        </Button>
      )}
    </div>
  );
}
