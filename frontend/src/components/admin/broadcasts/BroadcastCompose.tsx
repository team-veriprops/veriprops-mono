"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@3rdparty/ui/button";
import { Input } from "@3rdparty/ui/input";
import { Label } from "@3rdparty/ui/label";
import { Card } from "@3rdparty/ui/card";
import { toast } from "@components/3rdparty/ui/use-toast";
import { useBroadcastPreviewQuery, useComposeBroadcastMutation, useSendBroadcastMutation } from "./libs/useBroadcastQueries";
import { BroadcastAudience } from "@/types/broadcast";
import { ROUTES } from "@lib/routes";

const AUDIENCES = [
  BroadcastAudience.ALL,
  BroadcastAudience.CUSTOMERS,
  BroadcastAudience.AGENTS,
  BroadcastAudience.ADMINS,
];

/** Compose a broadcast (§18.1): audience + subject + body, preview the reach, send now or schedule. */
export default function BroadcastCompose() {
  const router = useRouter();
  const [audience, setAudience] = useState<BroadcastAudience>(BroadcastAudience.ALL);
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [scheduledAt, setScheduledAt] = useState("");

  const preview = useBroadcastPreviewQuery(audience);
  const compose = useComposeBroadcastMutation();
  const send = useSendBroadcastMutation();

  const canSubmit = subject.trim().length > 0 && body.trim().length > 0 && !compose.isPending;

  const submit = async (sendNow: boolean) => {
    if (!canSubmit) return;
    const res = await compose.mutateAsync({
      audience, subject: subject.trim(), body: body.trim(),
      scheduledAt: scheduledAt ? new Date(scheduledAt).toISOString() : undefined,
    });
    const id = res.data?.id;
    if (sendNow && id) {
      await send.mutateAsync(id);
      toast({ title: "Broadcast sent" });
    } else {
      toast({ title: scheduledAt ? "Broadcast scheduled" : "Draft saved" });
    }
    router.push(ROUTES.ADMIN.BROADCASTS);
  };

  return (
    <div className="mx-auto w-full max-w-2xl space-y-6 p-4 sm:p-6" data-testid="admin-broadcast-new">
      <h1 className="text-2xl font-bold text-foreground">New broadcast</h1>

      <Card className="space-y-4 p-5">
        <div>
          <Label>Audience</Label>
          <div className="mt-1 flex flex-wrap gap-2">
            {AUDIENCES.map((a) => (
              <button
                key={a}
                type="button"
                onClick={() => setAudience(a)}
                className={`rounded-full border px-3 py-1 text-sm ${audience === a ? "border-primary bg-primary/10" : "border-border"}`}
                data-testid={`broadcast-audience-${a.toLowerCase()}`}
              >
                {a}
              </button>
            ))}
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            {preview.data ? `${preview.data.recipientCount} recipients` : "Resolving reach…"}
          </p>
        </div>

        <div>
          <Label htmlFor="bc-subject">Subject</Label>
          <Input id="bc-subject" value={subject} onChange={(e) => setSubject(e.target.value)} data-testid="broadcast-subject" />
        </div>

        <div>
          <Label htmlFor="bc-body">Message</Label>
          <textarea
            id="bc-body"
            value={body}
            onChange={(e) => setBody(e.target.value)}
            rows={5}
            className="mt-1 w-full rounded-md border border-border bg-background p-2 text-sm"
            data-testid="broadcast-body"
          />
        </div>

        <div>
          <Label htmlFor="bc-schedule">Schedule (optional)</Label>
          <Input id="bc-schedule" type="datetime-local" value={scheduledAt} onChange={(e) => setScheduledAt(e.target.value)} data-testid="broadcast-schedule" />
        </div>

        {/* Preview */}
        <div className="rounded-md border border-dashed border-border p-3">
          <p className="text-xs font-semibold uppercase text-muted-foreground">Preview</p>
          <p className="mt-1 font-medium text-foreground">{subject || "Subject…"}</p>
          <p className="whitespace-pre-wrap text-sm text-muted-foreground">{body || "Message…"}</p>
        </div>

        <div className="flex gap-2">
          <Button onClick={() => submit(false)} disabled={!canSubmit} variant="outline" data-testid="broadcast-save">
            {scheduledAt ? "Schedule" : "Save draft"}
          </Button>
          <Button onClick={() => submit(true)} disabled={!canSubmit} data-testid="broadcast-send">
            Send now
          </Button>
        </div>
      </Card>
    </div>
  );
}
