"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Badge } from "@3rdparty/ui/badge";
import { Button } from "@3rdparty/ui/button";
import { Input } from "@3rdparty/ui/input";
import { Label } from "@3rdparty/ui/label";
import { Textarea } from "@3rdparty/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@3rdparty/ui/card";
import { Progress } from "@3rdparty/ui/progress";
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
import { VerificationStatus } from "@/types/verification";
import { TransactionCurrency } from "@/types/models";
import {
  AdminNoteCategory,
  ChargebackDto,
  ChargebackStatus,
  SlaHealth,
  TaskDto,
  TaskState,
  VerificationDetail,
} from "@/types/adminVerification";
import { useSuggestedAgentsQuery } from "@components/agents/reputation/libs/useReputationQueries";
import {
  useAddNoteMutation,
  useAdminVerificationDetailQuery,
  useAssignAgentMutation,
  useCancelMutation,
  usePauseMutation,
  useResolveChargebackMutation,
  useResumeMutation,
  useSetDelayMutation,
  useSubmitRebuttalMutation,
} from "./libs/useAdminVerificationQueries";

const formatMinor = (minor?: number, currency: TransactionCurrency = TransactionCurrency.NGN) =>
  minor === undefined
    ? "—"
    : new Intl.NumberFormat("en-NG", {
        style: "currency",
        currency,
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
      }).format(minor / 100);

const SLA_LABEL: Record<SlaHealth, string> = {
  [SlaHealth.ON_TRACK]: "On track",
  [SlaHealth.AT_RISK]: "At risk",
  [SlaHealth.OVERDUE]: "Overdue",
  [SlaHealth.NONE]: "No SLA",
};

// A task can be (re)assigned until it reaches SUBMITTED (§6.3).
const ASSIGNABLE_STATES = new Set<TaskState>([
  TaskState.PENDING,
  TaskState.ASSIGNED,
  TaskState.ACCEPTED,
  TaskState.IN_PROGRESS,
  TaskState.REJECTED,
]);

function TaskRow({
  task,
  verificationId,
}: {
  task: TaskDto;
  verificationId: string;
}) {
  const [agentId, setAgentId] = useState("");
  const [showSuggested, setShowSuggested] = useState(false);
  const assign = useAssignAgentMutation(verificationId);
  const suggested = useSuggestedAgentsQuery(showSuggested ? verificationId : null, showSuggested ? task.role : null);

  const doAssign = async (id: string) => {
    if (!id) return;
    await assign.mutateAsync({ role: task.role, agentId: id });
    toast({ title: `${task.role} assigned` });
    setAgentId("");
    setShowSuggested(false);
  };

  return (
    <div className="rounded-lg border border-border p-3" data-testid={`task-${task.role}`}>
      <div className="flex items-center justify-between">
        <span className="font-medium">{task.role}</span>
        <span className="flex items-center gap-2">
          <Badge variant="outline">{task.state}</Badge>
          {task.inPool && <Badge variant="secondary">In pool</Badge>}
        </span>
      </div>
      <p className="mt-1 text-sm text-muted-foreground">
        {task.assignedAgentId ? `Agent: ${task.assignedAgentId}` : "Unassigned"}
        {task.declineCount > 0 && ` · ${task.declineCount} decline(s)`}
      </p>
      {ASSIGNABLE_STATES.has(task.state) && (
        <>
          <div className="mt-2 flex gap-2">
            <Input
              placeholder="Agent ID"
              value={agentId}
              onChange={(e) => setAgentId(e.target.value)}
              data-testid={`assign-agent-${task.role}`}
            />
            <Button size="sm" onClick={() => doAssign(agentId)} disabled={assign.isPending || !agentId}>
              {task.assignedAgentId ? "Reassign" : "Assign"}
            </Button>
            <Button size="sm" variant="outline" onClick={() => setShowSuggested((v) => !v)}
              data-testid={`suggest-agents-${task.role}`}>
              {showSuggested ? "Hide" : "Suggest"}
            </Button>
          </div>
          {showSuggested && (
            <div className="mt-2 space-y-1" data-testid={`suggested-agents-${task.role}`}>
              {(suggested.data ?? []).length === 0 ? (
                <p className="text-xs text-muted-foreground">
                  {suggested.isLoading ? "Ranking eligible agents…" : "No eligible agents in coverage."}
                </p>
              ) : (
                (suggested.data ?? []).map((a) => (
                  <button key={a.userId} onClick={() => doAssign(a.userId)}
                    className="flex w-full items-center justify-between gap-2 rounded-md border p-2 text-left text-sm hover:bg-muted/50">
                    <span className="flex items-center gap-2">
                      <span className="font-medium">{a.name || a.userId.slice(0, 8)}</span>
                      {a.topAgent && <Badge variant="secondary">Top agent</Badge>}
                      {a.lowPerformance && <Badge variant="outline">Low</Badge>}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      score {a.compositeScore} · ★{a.accuracyScore.toFixed(1)} · {a.availability}
                      {a.coversArea ? " · in area" : ""}
                    </span>
                  </button>
                ))
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}

function ChargebackCard({
  chargeback,
  verificationId,
}: {
  chargeback: ChargebackDto;
  verificationId: string;
}) {
  const rebuttal = useSubmitRebuttalMutation(verificationId);
  const resolve = useResolveChargebackMutation(verificationId);

  return (
    <div className="rounded-lg border border-destructive/40 p-3" data-testid="chargeback-card">
      <div className="flex items-center justify-between">
        <span className="text-sm">
          {formatMinor(chargeback.amountMinor, chargeback.currency)} — {chargeback.reason ?? "—"}
        </span>
        <Badge variant="destructive">{chargeback.status}</Badge>
      </div>
      <div className="mt-2 flex flex-wrap gap-2">
        {chargeback.status === ChargebackStatus.FLAGGED && (
          <Button
            size="sm"
            onClick={async () => {
              await rebuttal.mutateAsync(chargeback.id);
              toast({ title: "Rebuttal pack submitted" });
            }}
            disabled={rebuttal.isPending}
            data-testid="chargeback-rebuttal"
          >
            Submit rebuttal
          </Button>
        )}
        {(chargeback.status === ChargebackStatus.FLAGGED ||
          chargeback.status === ChargebackStatus.REBUTTAL_SUBMITTED) && (
          <>
            <Button
              size="sm"
              variant="secondary"
              onClick={async () => {
                await resolve.mutateAsync({ chargebackId: chargeback.id, won: true });
                toast({ title: "Marked won" });
              }}
              disabled={resolve.isPending}
              data-testid="chargeback-won"
            >
              Mark won
            </Button>
            <Button
              size="sm"
              variant="destructive"
              onClick={async () => {
                await resolve.mutateAsync({ chargebackId: chargeback.id, won: false });
                toast({ title: "Marked lost" });
              }}
              disabled={resolve.isPending}
              data-testid="chargeback-lost"
            >
              Mark lost
            </Button>
          </>
        )}
      </div>
    </div>
  );
}

export default function AdminVerificationDetail({ verificationId }: { verificationId: string }) {
  const router = useRouter();
  const { data, isLoading, isError } = useAdminVerificationDetailQuery(verificationId);
  const pause = usePauseMutation(verificationId);
  const resume = useResumeMutation(verificationId);
  const cancel = useCancelMutation(verificationId);
  const setDelay = useSetDelayMutation(verificationId);
  const addNote = useAddNoteMutation(verificationId);

  const [cancelReason, setCancelReason] = useState("");
  const [delayDays, setDelayDays] = useState(1);
  const [noteBody, setNoteBody] = useState("");
  const [noteCategory, setNoteCategory] = useState<AdminNoteCategory>(AdminNoteCategory.OPERATIONAL);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16 text-muted-foreground">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" /> Loading verification…
      </div>
    );
  }
  if (isError || !data) {
    return <p className="py-16 text-center text-destructive">Failed to load verification.</p>;
  }

  const detail = data as VerificationDetail;
  const { summary } = detail;

  const onAddNote = async () => {
    if (!noteBody.trim()) return;
    await addNote.mutateAsync({ category: noteCategory, body: noteBody.trim() });
    toast({ title: "Note added" });
    setNoteBody("");
  };

  return (
    <div className="space-y-6" data-testid="admin-verification-detail">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">{summary.vid}</h1>
          <div className="mt-1 flex flex-wrap items-center gap-2">
            <Badge variant="outline">{summary.status}</Badge>
            {summary.tier && <Badge variant="secondary">{summary.tier}</Badge>}
            {summary.paused && <Badge variant="destructive">Paused</Badge>}
            <span className="text-sm text-muted-foreground">
              SLA: {SLA_LABEL[summary.slaHealth]}
              {summary.slaDueDate && ` · due ${summary.slaDueDate}`}
            </span>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="secondary"
            onClick={() => router.push(ROUTES.ADMIN.VERIFICATION_MESSAGES(verificationId))}
            data-testid="open-messages"
          >
            Messages
          </Button>
          <a
            href={ROUTES.ADMIN.VERIFICATION_AUDIT_EXPORT(verificationId)}
            target="_blank"
            rel="noopener noreferrer"
            data-testid="export-audit-pack"
          >
            <Button variant="outline">Export audit pack</Button>
          </a>
          {(summary.status === VerificationStatus.UNDER_REVIEW ||
            summary.status === VerificationStatus.COMPLETED) && (
            <Button
              onClick={() => router.push(ROUTES.ADMIN.REPORT_REVIEW(verificationId))}
              data-testid="open-report-review"
            >
              Report review
            </Button>
          )}
          {summary.paused ? (
            <Button variant="secondary" onClick={() => resume.mutate()} disabled={resume.isPending}>
              Resume
            </Button>
          ) : (
            <Button variant="secondary" onClick={() => pause.mutate()} disabled={pause.isPending}>
              Pause
            </Button>
          )}
        </div>
      </div>

      {/* Progress */}
      <Card>
        <CardContent className="space-y-2 p-6">
          <div className="flex items-center justify-between text-sm">
            <span>
              Task progress — {detail.approvedTaskCount}/{detail.requiredTaskCount} approved
            </span>
            <span className="text-muted-foreground">{detail.progressPercent}%</span>
          </div>
          <Progress value={detail.progressPercent} />
        </CardContent>
      </Card>

      {/* Tasks */}
      <Card>
        <CardHeader>
          <CardTitle>Tasks</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {detail.tasks.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No tasks yet — they are instantiated at PAID.
            </p>
          ) : (
            detail.tasks.map((t) => (
              <TaskRow key={t.id} task={t} verificationId={verificationId} />
            ))
          )}
        </CardContent>
      </Card>

      {/* Property + Payments */}
      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Property</CardTitle>
          </CardHeader>
          <CardContent className="text-sm">
            {detail.property ? (
              <div className="space-y-1">
                <p>{detail.property.address ?? "—"}</p>
                <p className="text-muted-foreground">
                  {detail.property.propertyType} · {detail.property.state ?? "—"}
                </p>
              </div>
            ) : (
              <p className="text-muted-foreground">No property linked.</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Payments</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {detail.payments.length === 0 ? (
              <p className="text-muted-foreground">No payments.</p>
            ) : (
              detail.payments.map((p) => (
                <div key={p.id} className="flex items-center justify-between">
                  <span>{formatMinor(p.amountMinor, p.currency)}</span>
                  <Badge variant="outline">{p.status}</Badge>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>

      {/* Commissions + Chargebacks */}
      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Commissions</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {detail.commissions.length === 0 ? (
              <p className="text-muted-foreground">No commissions accrued yet.</p>
            ) : (
              detail.commissions.map((c) => (
                <div key={c.id} className="flex items-center justify-between">
                  <span>
                    {c.role} — {formatMinor(c.amountMinor, c.currency)}
                  </span>
                  <Badge variant="outline">{c.status}</Badge>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Chargebacks</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {detail.chargebacks.length === 0 ? (
              <p className="text-sm text-muted-foreground">No chargebacks.</p>
            ) : (
              detail.chargebacks.map((c) => (
                <ChargebackCard key={c.id} chargeback={c} verificationId={verificationId} />
              ))
            )}
          </CardContent>
        </Card>
      </div>

      {/* Notes */}
      <Card>
        <CardHeader>
          <CardTitle>Internal notes</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <div className="flex gap-2">
              <Select
                value={noteCategory}
                onValueChange={(v) => setNoteCategory(v as AdminNoteCategory)}
              >
                <SelectTrigger className="w-44" data-testid="note-category">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.values(AdminNoteCategory).map((c) => (
                    <SelectItem key={c} value={c}>
                      {c}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Textarea
              placeholder="Add an internal note (never shown to customers/agents)…"
              value={noteBody}
              onChange={(e) => setNoteBody(e.target.value)}
              data-testid="note-body"
            />
            <Button onClick={onAddNote} disabled={addNote.isPending || !noteBody.trim()} data-testid="note-submit">
              Add note
            </Button>
          </div>

          <div className="space-y-2">
            {detail.notes.map((n) => (
              <div key={n.id} className="rounded border border-border p-2 text-sm">
                <div className="flex items-center gap-2">
                  <Badge variant="secondary">{n.category}</Badge>
                  {n.pinned && <Badge>Pinned</Badge>}
                  <span className="text-muted-foreground">{n.dateCreated?.slice(0, 10)}</span>
                </div>
                <p className="mt-1">{n.body}</p>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Danger zone: delay + cancel */}
      <Card>
        <CardHeader>
          <CardTitle>Operational actions</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-6 md:grid-cols-2">
          <div className="space-y-2">
            <Label>Extend SLA (business days)</Label>
            <div className="flex gap-2">
              <Input
                type="number"
                min={1}
                value={delayDays}
                onChange={(e) => setDelayDays(Number(e.target.value))}
                className="w-24"
                data-testid="delay-days"
              />
              <Button
                variant="secondary"
                onClick={async () => {
                  await setDelay.mutateAsync({ extraBusinessDays: delayDays });
                  toast({ title: "SLA extended" });
                }}
                disabled={setDelay.isPending || !summary.slaDueDate}
              >
                Extend
              </Button>
            </div>
            {!summary.slaDueDate && (
              <p className="text-xs text-muted-foreground">No SLA clock until PAID.</p>
            )}
          </div>

          <div className="space-y-2">
            <Label>Cancel verification</Label>
            <div className="flex gap-2">
              <Input
                placeholder="Reason"
                value={cancelReason}
                onChange={(e) => setCancelReason(e.target.value)}
                data-testid="cancel-reason"
              />
              <Button
                variant="destructive"
                onClick={async () => {
                  await cancel.mutateAsync({ reason: cancelReason });
                  toast({ title: "Verification cancelled" });
                  setCancelReason("");
                }}
                disabled={cancel.isPending || !cancelReason.trim()}
                data-testid="cancel-submit"
              >
                Cancel
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
