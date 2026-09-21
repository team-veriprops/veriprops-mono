"use client";

import { useMemo, useState } from "react";
import { Badge } from "@3rdparty/ui/badge";
import { Button } from "@3rdparty/ui/button";
import { Input } from "@3rdparty/ui/input";
import { Label } from "@3rdparty/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@3rdparty/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@3rdparty/ui/select";
import { toast } from "@components/3rdparty/ui/use-toast";
import { Loader2 } from "lucide-react";
import Link from "next/link";
import { ROUTES } from "@lib/routes";
import { humanizeEnumLabel } from "@lib/utils";
import { TaskState } from "@/types/adminVerification";
import { EvidenceKind, ROLE_FORM_FIELDS } from "@/types/agentTask";
import {
  useAcceptTaskMutation,
  useAgentTasksQuery,
  useStartTaskMutation,
  useSubmitTaskMutation,
  useTaskEvidenceQuery,
  useUploadEvidenceMutation,
} from "./libs/useAgentTaskQueries";

/** Best-effort GPS hint; the backend stamps the authoritative capture location (§12.3). */
function useGeolocationHint() {
  return async (): Promise<{ latitude: number; longitude: number } | undefined> =>
    new Promise((resolve) => {
      if (!navigator.geolocation) return resolve(undefined);
      navigator.geolocation.getCurrentPosition(
        (pos) => resolve({ latitude: pos.coords.latitude, longitude: pos.coords.longitude }),
        () => resolve(undefined),
        { timeout: 5000 },
      );
    });
}

export default function AgentTaskDetail({ taskId }: { taskId: string }) {
  const { data, isLoading } = useAgentTasksQuery(undefined, 0, 100);
  const task = useMemo(() => data?.items.find((t) => t.id === taskId), [data, taskId]);

  const { data: evidence } = useTaskEvidenceQuery(taskId);
  const accept = useAcceptTaskMutation();
  const start = useStartTaskMutation();
  const upload = useUploadEvidenceMutation(taskId);
  const submit = useSubmitTaskMutation();
  const getGps = useGeolocationHint();

  const [kind, setKind] = useState<EvidenceKind>(EvidenceKind.PHOTO);
  const [form, setForm] = useState<Record<string, string>>({});

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16 text-muted-foreground">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" /> Loading task…
      </div>
    );
  }
  if (!task) {
    return <p className="py-16 text-center text-destructive">Task not found.</p>;
  }

  const fields = ROLE_FORM_FIELDS[task.role] ?? [];
  const missingRequired = fields.filter((f) => f.required && !form[f.key]?.trim());
  const evidenceCount = evidence?.length ?? task.evidenceCount;

  const onUpload = async (file: File) => {
    const gps = await getGps();
    await upload.mutateAsync({ file, kind, gps });
    toast({ title: "Evidence uploaded" });
  };

  const onSubmit = async () => {
    const payload: Record<string, unknown> = {};
    for (const f of fields) if (form[f.key]?.trim()) payload[f.key] = form[f.key].trim();
    await submit.mutateAsync({ taskId, payload });
    toast({ title: "Task submitted for review" });
  };

  return (
    <div className="space-y-6" data-testid="agent-task-detail">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-foreground">{humanizeEnumLabel(task.role)} task</h1>
          <div className="mt-1 flex items-center gap-2">
            <Badge variant="outline">{humanizeEnumLabel(task.state)}</Badge>
            <Badge variant="secondary">{humanizeEnumLabel(task.tier)}</Badge>
          </div>
        </div>
        <div className="flex gap-2">
          <Button asChild variant="secondary" data-testid="detail-messages">
            <Link href={ROUTES.AGENT.TASK_MESSAGES(task.id)}>Messages</Link>
          </Button>
          <Button asChild variant="outline" data-testid="detail-history">
            <Link href={ROUTES.AGENT.TASK_HISTORY(task.id)}>History</Link>
          </Button>
          {(task.state === TaskState.PENDING || task.inPool) && (
            <Button
              onClick={async () => {
                await accept.mutateAsync(task.id);
                toast({ title: "Accepted" });
              }}
              disabled={accept.isPending}
              data-testid="detail-accept"
            >
              Accept
            </Button>
          )}
          {task.state === TaskState.ACCEPTED && (
            <Button
              onClick={async () => {
                await start.mutateAsync(task.id);
                toast({ title: "Work started" });
              }}
              disabled={start.isPending}
              data-testid="detail-start"
            >
              Start work
            </Button>
          )}
        </div>
      </div>

      {task.rejectionReason && (
        <Card className="border-destructive/40">
          <CardContent className="p-4 text-sm">
            <span className="font-medium text-destructive">Returned for rework: </span>
            {task.rejectionReason}
          </CardContent>
        </Card>
      )}

      {task.state === TaskState.IN_PROGRESS && (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Evidence ({evidenceCount})</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {/* TODO(gap): evidence capture is a plain file input straight to the backend.
                  Field agents work on patchy mobile networks, so this flow still needs an
                  offline retry queue and client-side image compression before upload — neither
                  is built — PRD "Known Gaps & Roadmap". */}
              <div className="flex flex-wrap items-end gap-2">
                <div className="space-y-1">
                  <Label>Kind</Label>
                  <Select value={kind} onValueChange={(v) => setKind(v as EvidenceKind)}>
                    <SelectTrigger className="w-40" data-testid="evidence-kind">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {Object.values(EvidenceKind).map((k) => (
                        <SelectItem key={k} value={k}>
                          {humanizeEnumLabel(k)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <Input
                  type="file"
                  onChange={(e) => e.target.files?.[0] && onUpload(e.target.files[0])}
                  disabled={upload.isPending}
                  data-testid="evidence-file"
                />
              </div>
              <div className="space-y-1">
                {(evidence ?? []).map((e) => (
                  <div key={e.id} className="flex items-center justify-between rounded border border-border p-2 text-sm">
                    <span>
                      <Badge variant="secondary">{humanizeEnumLabel(e.kind)}</Badge>{" "}
                      <span className="font-mono text-xs text-muted-foreground">
                        {e.contentSha256.slice(0, 12)}…
                      </span>
                    </span>
                    {e.gpsLatitude != null && (
                      <span className="text-xs text-muted-foreground">
                        {e.gpsLatitude.toFixed(4)}, {e.gpsLongitude?.toFixed(4)}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>{humanizeEnumLabel(task.role)} findings</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {fields.map((f) => (
                <div key={f.key} className="space-y-1">
                  <Label>
                    {f.label}
                    {f.required && <span className="text-destructive"> *</span>}
                  </Label>
                  <Input
                    value={form[f.key] ?? ""}
                    onChange={(e) => setForm((s) => ({ ...s, [f.key]: e.target.value }))}
                    data-testid={`field-${f.key}`}
                  />
                </div>
              ))}
              <Button
                onClick={onSubmit}
                disabled={submit.isPending || missingRequired.length > 0 || evidenceCount === 0}
                data-testid="detail-submit"
              >
                Submit for review
              </Button>
              {evidenceCount === 0 && (
                <p className="text-xs text-muted-foreground">
                  Upload at least one piece of evidence before submitting.
                </p>
              )}
            </CardContent>
          </Card>
        </>
      )}

      {task.state === TaskState.SUBMITTED && (
        <Card>
          <CardContent className="p-6 text-sm text-muted-foreground">
            Submitted — awaiting admin review.
          </CardContent>
        </Card>
      )}
    </div>
  );
}
