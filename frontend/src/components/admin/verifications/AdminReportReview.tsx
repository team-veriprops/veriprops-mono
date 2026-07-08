"use client";

import { useState } from "react";
import { Badge } from "@3rdparty/ui/badge";
import { Button } from "@3rdparty/ui/button";
import { Input } from "@3rdparty/ui/input";
import { Label } from "@3rdparty/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@3rdparty/ui/card";
import { toast } from "@components/3rdparty/ui/use-toast";
import { Loader2 } from "lucide-react";
import { humanizeEnumLabel } from "@lib/utils";
import { AgentRole } from "@/types/agent";
import { TaskState } from "@/types/adminVerification";
import { ReviewState } from "@/types/adminReview";
import {
  useApproveTaskMutation,
  useFailMutation,
  useRejectTaskMutation,
  useReleaseMutation,
  useReopenTaskMutation,
  useReviewQuery,
} from "./libs/useReviewQueries";

function ReviewTaskRow({ verificationId, task, findings }: {
  verificationId: string;
  task: { id: string; role: AgentRole; state: TaskState; reviewDecision?: string };
  findings?: Record<string, unknown> | null;
}) {
  const approve = useApproveTaskMutation(verificationId);
  const reject = useRejectTaskMutation(verificationId);
  const reopen = useReopenTaskMutation(verificationId);
  const [quality, setQuality] = useState(100);
  const [reason, setReason] = useState("");

  const reviewed = (task as { reviewDecision?: string }).reviewDecision;

  return (
    <div className="rounded-lg border border-border p-3" data-testid={`review-task-${task.role}`}>
      <div className="flex items-center justify-between">
        <span className="font-medium">{humanizeEnumLabel(task.role)}</span>
        <span className="flex items-center gap-2">
          <Badge variant="outline">{humanizeEnumLabel(task.state)}</Badge>
          {reviewed && (
            <Badge variant={reviewed === TaskState.APPROVED ? "secondary" : "destructive"}>
              {humanizeEnumLabel(reviewed)}
            </Badge>
          )}
        </span>
      </div>

      {findings && (
        <pre className="mt-2 max-h-32 overflow-auto rounded bg-muted p-2 text-xs">
          {JSON.stringify(findings, null, 2)}
        </pre>
      )}

      {task.state === TaskState.SUBMITTED && (
        <div className="mt-2 flex flex-wrap items-end gap-2">
          <div className="space-y-1">
            <Label className="text-xs">Quality (0–100)</Label>
            <Input
              type="number"
              min={0}
              max={100}
              value={quality}
              onChange={(e) => setQuality(Number(e.target.value))}
              className="w-24"
              data-testid={`quality-${task.role}`}
            />
          </div>
          <Button
            size="sm"
            onClick={async () => {
              await approve.mutateAsync({ role: task.role, quality });
              toast({ title: `${humanizeEnumLabel(task.role)} approved` });
            }}
            disabled={approve.isPending}
            data-testid={`approve-${task.role}`}
          >
            Approve
          </Button>
          <Input
            placeholder="Reject reason"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            className="w-48"
            data-testid={`reject-reason-${task.role}`}
          />
          <Button
            size="sm"
            variant="destructive"
            onClick={async () => {
              await reject.mutateAsync({ role: task.role, reason });
              toast({ title: `${humanizeEnumLabel(task.role)} sent to rework` });
              setReason("");
            }}
            disabled={reject.isPending || !reason.trim()}
            data-testid={`reject-${task.role}`}
          >
            Reject
          </Button>
        </div>
      )}

      {task.state === TaskState.APPROVED && (
        <Button
          size="sm"
          variant="ghost"
          className="mt-2"
          onClick={async () => {
            await reopen.mutateAsync({ role: task.role });
            toast({ title: `${humanizeEnumLabel(task.role)} reopened` });
          }}
          disabled={reopen.isPending}
          data-testid={`reopen-${task.role}`}
        >
          Reopen
        </Button>
      )}
    </div>
  );
}

export default function AdminReportReview({ verificationId }: { verificationId: string }) {
  const { data, isLoading, isError } = useReviewQuery(verificationId);
  const release = useReleaseMutation(verificationId);
  const fail = useFailMutation(verificationId);
  const [releaseReason, setReleaseReason] = useState("");
  const [failReason, setFailReason] = useState("");

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16 text-muted-foreground">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" /> Loading review…
      </div>
    );
  }
  if (isError || !data) {
    return <p className="py-16 text-center text-destructive">Failed to load review.</p>;
  }

  const review = data as ReviewState;

  return (
    <div className="space-y-6" data-testid="admin-report-review">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Report review</h1>
          <div className="mt-1 flex items-center gap-2">
            <Badge variant="outline">{humanizeEnumLabel(review.status)}</Badge>
            {review.tier && <Badge variant="secondary">{humanizeEnumLabel(review.tier)}</Badge>}
            {review.projectedTrustScore != null && (
              <Badge>Trust score: {review.projectedTrustScore}</Badge>
            )}
          </div>
        </div>
      </div>

      {review.conflicts.length > 0 && (
        <Card className="border-destructive/40">
          <CardHeader>
            <CardTitle className="text-destructive">Conflicts</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {review.conflicts.map((c, i) => (
              <div key={i} className="text-sm" data-testid="review-conflict">
                <Badge variant={c.severity === "HIGH" ? "destructive" : "secondary"}>{c.severity}</Badge>{" "}
                {c.message}
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Task submissions</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {review.tasks.map((t) => (
            <ReviewTaskRow
              key={t.id}
              verificationId={verificationId}
              task={t as { id: string; role: AgentRole; state: TaskState; reviewDecision?: string }}
              findings={review.findings?.[t.role]}
            />
          ))}
        </CardContent>
      </Card>

      {review.report && (
        <Card>
          <CardContent className="p-4 text-sm">
            Released report v{review.report.reportVersion} — trust score{" "}
            {review.report.compositeTrustScore} ({review.report.state})
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Release</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-6 md:grid-cols-2">
          <div className="space-y-2">
            <Label>Release report</Label>
            <Input
              placeholder="Reason (optional)"
              value={releaseReason}
              onChange={(e) => setReleaseReason(e.target.value)}
              data-testid="release-reason"
            />
            <Button
              onClick={async () => {
                await release.mutateAsync({ reason: releaseReason || undefined });
                toast({ title: "Report released" });
              }}
              disabled={release.isPending || !review.releasable}
              data-testid="release-submit"
            >
              Release report
            </Button>
            {!review.releasable && (
              <p className="text-xs text-muted-foreground">
                Approve every task and resolve high-severity conflicts to enable release.
              </p>
            )}
          </div>

          <div className="space-y-2">
            <Label>Fail &amp; refund</Label>
            <Input
              placeholder="Reason"
              value={failReason}
              onChange={(e) => setFailReason(e.target.value)}
              data-testid="fail-reason"
            />
            <Button
              variant="destructive"
              onClick={async () => {
                await fail.mutateAsync({ reason: failReason });
                toast({ title: "Verification failed & refunded" });
                setFailReason("");
              }}
              disabled={fail.isPending || !failReason.trim()}
              data-testid="fail-submit"
            >
              Fail &amp; refund
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
