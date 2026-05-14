"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  useCreateBroadcastMutation,
  useScheduleBroadcastMutation,
  useSendBroadcastNowMutation,
} from "@components/admin/libs/useAdminQueries";
import type { BroadcastAudience, BroadcastDto } from "@components/admin/libs/admin-service";
import { getErrorMessage } from "@lib/utils";
import { ROUTES } from "@lib/routes";

type Step = "audience" | "compose" | "preview" | "dispatch";

const composeSchema = z.object({
  subject: z.string().min(1, "Subject is required"),
  bodyText: z.string().min(1, "Message body is required"),
  bodyHtml: z.string().optional(),
});
type ComposeValues = z.infer<typeof composeSchema>;

const AUDIENCES: { value: BroadcastAudience; label: string; desc: string }[] = [
  { value: "ALL", label: "All Users", desc: "Sends to every registered customer and agent." },
  { value: "CUSTOMERS", label: "Customers Only", desc: "Only users who have started or completed a verification." },
  { value: "AGENTS", label: "Agents Only", desc: "Only verified field agents on the platform." },
];

export default function BroadcastComposer() {
  const router = useRouter();
  const [step, setStep] = useState<Step>("audience");
  const [audience, setAudience] = useState<BroadcastAudience>("ALL");
  const [created, setCreated] = useState<BroadcastDto | null>(null);
  const [scheduleDate, setScheduleDate] = useState("");
  const [error, setError] = useState<string | null>(null);

  const createMutation = useCreateBroadcastMutation();
  const scheduleMutation = useScheduleBroadcastMutation();
  const sendNowMutation = useSendBroadcastNowMutation();

  const {
    register,
    handleSubmit,
    getValues,
    formState: { errors },
  } = useForm<ComposeValues>({
    resolver: zodResolver(composeSchema),
  });

  const handleAudienceNext = () => setStep("compose");

  const handleCompose = handleSubmit(async (values) => {
    setError(null);
    try {
      const res = await createMutation.mutateAsync({
        subject: values.subject,
        bodyText: values.bodyText,
        bodyHtml: values.bodyHtml || undefined,
        audience,
      });
      setCreated(res.data as unknown as BroadcastDto);
      setStep("preview");
    } catch (e) {
      setError(getErrorMessage(e as Error));
    }
  });

  const handleSendNow = async () => {
    if (!created) return;
    setError(null);
    try {
      await sendNowMutation.mutateAsync(created.id);
      router.push(ROUTES.ADMIN.BROADCASTS);
    } catch (e) {
      setError(getErrorMessage(e as Error));
    }
  };

  const handleSchedule = async () => {
    if (!created || !scheduleDate) return;
    setError(null);
    try {
      await scheduleMutation.mutateAsync({ broadcastId: created.id, scheduledAt: new Date(scheduleDate).toISOString() });
      router.push(ROUTES.ADMIN.BROADCASTS);
    } catch (e) {
      setError(getErrorMessage(e as Error));
    }
  };

  const STEPS: { key: Step; label: string }[] = [
    { key: "audience", label: "Audience" },
    { key: "compose", label: "Compose" },
    { key: "preview", label: "Preview" },
    { key: "dispatch", label: "Send" },
  ];
  const stepIndex = STEPS.findIndex((s) => s.key === step);

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* Stepper */}
      <div className="flex items-center gap-0">
        {STEPS.map((s, i) => (
          <div key={s.key} className="flex items-center flex-1">
            <div className="flex items-center gap-2">
              <div
                className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold shrink-0"
                style={{
                  background: i <= stepIndex ? "var(--brand-viridian)" : "rgba(196,198,207,0.3)",
                  color: i <= stepIndex ? "white" : "var(--brand-on-surface-variant)",
                }}
              >
                {i + 1}
              </div>
              <span
                className="text-xs font-medium hidden sm:block"
                style={{ color: i <= stepIndex ? "var(--brand-viridian)" : "var(--brand-on-surface-variant)" }}
              >
                {s.label}
              </span>
            </div>
            {i < STEPS.length - 1 && (
              <div
                className="flex-1 h-px mx-2"
                style={{ background: i < stepIndex ? "var(--brand-viridian)" : "rgba(196,198,207,0.3)" }}
              />
            )}
          </div>
        ))}
      </div>

      {/* Step: Audience */}
      {step === "audience" && (
        <div className="space-y-4">
          <h3 className="text-base font-semibold" style={{ color: "var(--brand-navy)" }}>Who receives this broadcast?</h3>
          <div className="space-y-2">
            {AUDIENCES.map((a) => (
              <label
                key={a.value}
                style={{ cursor: "pointer" }}
                className={`flex items-start gap-3 rounded-xl border p-4 transition-colors ${
                  audience === a.value ? "border-green-400 bg-green-50" : "border-gray-200 hover:bg-gray-50"
                }`}
              >
                <input
                  type="radio"
                  name="audience"
                  value={a.value}
                  checked={audience === a.value}
                  onChange={() => setAudience(a.value)}
                  className="mt-0.5"
                />
                <div>
                  <p className="text-sm font-medium" style={{ color: "var(--brand-navy)" }}>{a.label}</p>
                  <p className="text-xs mt-0.5" style={{ color: "var(--brand-on-surface-variant)" }}>{a.desc}</p>
                </div>
              </label>
            ))}
          </div>
          <div className="flex justify-end">
            <button
              type="button"
              onClick={handleAudienceNext}
              className="px-6 py-2 rounded-lg text-sm font-medium text-white"
              style={{ background: "var(--brand-viridian)" }}
            >
              Next: Compose
            </button>
          </div>
        </div>
      )}

      {/* Step: Compose */}
      {step === "compose" && (
        <form onSubmit={handleCompose} className="space-y-4">
          <h3 className="text-base font-semibold" style={{ color: "var(--brand-navy)" }}>Write your message</h3>
          <div>
            <label className="block text-xs font-medium mb-1" style={{ color: "var(--brand-on-surface-variant)" }}>
              Subject
            </label>
            <input
              {...register("subject")}
              type="text"
              placeholder="e.g. Important update for Veriprops users"
              className="w-full rounded-lg px-3 py-2 text-sm border"
              style={{ borderColor: "rgba(196,198,207,0.4)", color: "var(--brand-navy)", background: "var(--brand-surface)" }}
            />
            {errors.subject && <p className="text-xs text-red-500 mt-1">{errors.subject.message}</p>}
          </div>
          <div>
            <label className="block text-xs font-medium mb-1" style={{ color: "var(--brand-on-surface-variant)" }}>
              Message Body
            </label>
            <textarea
              {...register("bodyText")}
              rows={8}
              placeholder="Write your broadcast message here…"
              className="w-full rounded-lg px-3 py-2 text-sm border resize-none"
              style={{ borderColor: "rgba(196,198,207,0.4)", color: "var(--brand-navy)", background: "var(--brand-surface)" }}
            />
            {errors.bodyText && <p className="text-xs text-red-500 mt-1">{errors.bodyText.message}</p>}
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <div className="flex justify-between">
            <button
              type="button"
              onClick={() => setStep("audience")}
              className="px-4 py-2 rounded-lg text-sm border"
              style={{ borderColor: "rgba(196,198,207,0.4)", color: "var(--brand-on-surface-variant)" }}
            >
              Back
            </button>
            <button
              type="submit"
              disabled={createMutation.isPending}
              className="px-6 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
              style={{ background: "var(--brand-viridian)" }}
            >
              {createMutation.isPending ? "Saving…" : "Next: Preview"}
            </button>
          </div>
        </form>
      )}

      {/* Step: Preview */}
      {step === "preview" && created && (
        <div className="space-y-4">
          <h3 className="text-base font-semibold" style={{ color: "var(--brand-navy)" }}>Preview</h3>
          <div
            className="rounded-xl p-5 space-y-3"
            style={{ border: "1px solid rgba(196,198,207,0.3)", background: "rgba(63,102,83,0.02)" }}
          >
            <div className="flex items-center gap-2">
              <span className="text-xs font-medium" style={{ color: "var(--brand-on-surface-variant)" }}>To:</span>
              <span className="text-xs" style={{ color: "var(--brand-navy)" }}>{AUDIENCES.find((a) => a.value === audience)?.label}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-medium" style={{ color: "var(--brand-on-surface-variant)" }}>Subject:</span>
              <span className="text-sm font-semibold" style={{ color: "var(--brand-navy)" }}>{created.subject}</span>
            </div>
            <div
              className="rounded-lg p-4 text-sm whitespace-pre-wrap"
              style={{ background: "var(--brand-surface)", color: "var(--brand-navy)", border: "1px solid rgba(196,198,207,0.2)" }}
            >
              {created.bodyText}
            </div>
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <div className="flex justify-between">
            <button
              type="button"
              onClick={() => setStep("compose")}
              className="px-4 py-2 rounded-lg text-sm border"
              style={{ borderColor: "rgba(196,198,207,0.4)", color: "var(--brand-on-surface-variant)" }}
            >
              Back
            </button>
            <button
              type="button"
              onClick={() => setStep("dispatch")}
              className="px-6 py-2 rounded-lg text-sm font-medium text-white"
              style={{ background: "var(--brand-viridian)" }}
            >
              Next: Send
            </button>
          </div>
        </div>
      )}

      {/* Step: Dispatch */}
      {step === "dispatch" && created && (
        <div className="space-y-5">
          <h3 className="text-base font-semibold" style={{ color: "var(--brand-navy)" }}>Send or Schedule</h3>

          {/* Send Now */}
          <div
            className="rounded-xl p-5 space-y-3"
            style={{ border: "1px solid rgba(196,198,207,0.3)" }}
          >
            <p className="text-sm font-medium" style={{ color: "var(--brand-navy)" }}>Send Immediately</p>
            <p className="text-xs" style={{ color: "var(--brand-on-surface-variant)" }}>
              Deliver to all recipients right now.
            </p>
            <button
              type="button"
              onClick={handleSendNow}
              disabled={sendNowMutation.isPending}
              className="px-5 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
              style={{ background: "#10b981" }}
            >
              {sendNowMutation.isPending ? "Sending…" : "Send Now"}
            </button>
          </div>

          {/* Schedule */}
          <div
            className="rounded-xl p-5 space-y-3"
            style={{ border: "1px solid rgba(196,198,207,0.3)" }}
          >
            <p className="text-sm font-medium" style={{ color: "var(--brand-navy)" }}>Schedule for Later</p>
            <input
              type="datetime-local"
              value={scheduleDate}
              onChange={(e) => setScheduleDate(e.target.value)}
              className="rounded-lg px-3 py-2 text-sm border"
              style={{ borderColor: "rgba(196,198,207,0.4)", color: "var(--brand-navy)", background: "var(--brand-surface)" }}
            />
            <div>
              <button
                type="button"
                onClick={handleSchedule}
                disabled={!scheduleDate || scheduleMutation.isPending}
                className="px-5 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
                style={{ background: "var(--brand-viridian)" }}
              >
                {scheduleMutation.isPending ? "Scheduling…" : "Schedule Broadcast"}
              </button>
            </div>
          </div>

          {error && <p className="text-sm text-red-600">{error}</p>}

          <button
            type="button"
            onClick={() => setStep("preview")}
            className="text-sm"
            style={{ color: "var(--brand-on-surface-variant)" }}
          >
            ← Back to Preview
          </button>
        </div>
      )}
    </div>
  );
}
