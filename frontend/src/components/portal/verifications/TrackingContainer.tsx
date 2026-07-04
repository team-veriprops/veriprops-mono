"use client";

import Link from "next/link";
import { BadgeCheck, ShieldCheck } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@3rdparty/ui/card";
import { CopyText } from "@components/ui/CopyText";
import { AsyncStateComponent } from "@components/ui/AsyncStateComponent";
import { ROUTES } from "@lib/routes";
import { useVerificationTracking } from "@components/portal/libs/useVerificationQueries";
import { VerificationStatus } from "@/types/verification";
import { VerificationTracking } from "@/types/tracking";
import { VerificationStatusBadge } from "./VerificationStatusBadge";
import { VerificationProgress } from "./VerificationProgress";
import { EvidenceGallery } from "./EvidenceGallery";

// State-specific reassurance copy (§9.3) — frames each phase in plain, calming language.
const STATE_REASSURANCE: Partial<Record<VerificationStatus, string>> = {
  [VerificationStatus.PAID]:
    "Payment confirmed — we're assigning your verification agents. Work usually starts within 24 hours.",
  [VerificationStatus.IN_PROGRESS]:
    "Your agents are on the ground. As each stage clears, you'll see it below.",
  [VerificationStatus.UNDER_REVIEW]:
    "All checks are in. Our team is doing a final quality review before releasing your report — this is intentional and protects the integrity of your result.",
};

export default function TrackingContainer({ verificationId }: { verificationId: string }) {
  const { data, isLoading, isError } = useVerificationTracking(verificationId);

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4 sm:p-6" data-testid="verify-tracking">
      <AsyncStateComponent<VerificationTracking>
        isLoading={isLoading}
        isError={isError}
        data={data}
        loadingText="Loading your verification…"
      >
        {(t) => (
          <>
            <Header tracking={t} />
            {STATE_REASSURANCE[t.status] && (
              <div className="flex items-start gap-2 rounded-lg border bg-muted/40 p-3 text-sm">
                <ShieldCheck className="mt-0.5 size-4 shrink-0 text-primary" />
                <p>{STATE_REASSURANCE[t.status]}</p>
              </div>
            )}

            <SlaCard tracking={t} />

            <Card>
              <CardHeader><CardTitle className="text-base">Progress</CardTitle></CardHeader>
              <CardContent>
                <VerificationProgress tasks={t.tasks} progressPercent={t.progressPercent} />
              </CardContent>
            </Card>

            {t.interimMilestones.length > 0 && (
              <Card>
                <CardHeader><CardTitle className="text-base">What we&apos;ve found so far</CardTitle></CardHeader>
                <CardContent className="space-y-3">
                  {t.interimMilestones.map((m) => (
                    <div key={m.role} className="flex items-start gap-2 text-sm">
                      <BadgeCheck className="mt-0.5 size-4 shrink-0 text-primary" />
                      <div>
                        <p>{m.message}</p>
                        {m.note && <p className="text-muted-foreground">{m.note}</p>}
                      </div>
                    </div>
                  ))}
                </CardContent>
              </Card>
            )}

            {t.agents.length > 0 && (
              <Card>
                <CardHeader><CardTitle className="text-base">Your agents</CardTitle></CardHeader>
                <CardContent className="flex flex-wrap gap-3">
                  {t.agents.map((a, i) => (
                    <div key={`${a.role}-${i}`} className="flex items-center gap-2 rounded-lg border px-3 py-2 text-sm">
                      <span className="font-medium">{a.firstName}</span>
                      <span className="text-muted-foreground">· {a.role}</span>
                      {a.verified && <BadgeCheck className="size-4 text-primary" aria-label="Verified" />}
                    </div>
                  ))}
                </CardContent>
              </Card>
            )}

            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle className="text-base">Evidence</CardTitle>
                <Link
                  href={ROUTES.PORTAL.VERIFICATION_EVIDENCE(verificationId)}
                  className="text-sm text-primary hover:underline"
                >
                  View all
                </Link>
              </CardHeader>
              <CardContent>
                {t.evidencePreview.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    Evidence appears here as each stage is reviewed and approved.
                  </p>
                ) : (
                  <EvidenceGallery items={t.evidencePreview} />
                )}
              </CardContent>
            </Card>
          </>
        )}
      </AsyncStateComponent>
    </div>
  );
}

function Header({ tracking: t }: { tracking: VerificationTracking }) {
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <VerificationStatusBadge status={t.status} label={t.statusLabel} />
        {t.tier && <span className="text-xs text-muted-foreground">{t.tier} tier</span>}
      </div>
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <span>Verification ID</span>
        <CopyText text={t.vid} />
      </div>
      {t.address && <p className="text-sm font-medium">{t.address}</p>}
    </div>
  );
}

function SlaCard({ tracking: t }: { tracking: VerificationTracking }) {
  const { sla } = t;
  if (!sla.expectedDate && !sla.label) return null;
  return (
    <Card>
      <CardContent className="flex flex-wrap items-center justify-between gap-3 pt-6 text-sm">
        <div>
          <p className="text-muted-foreground">Expected completion</p>
          <p className="font-medium">
            {sla.expectedDate ? new Date(sla.expectedDate).toLocaleDateString() : "—"}
          </p>
        </div>
        {sla.totalBusinessDays != null && (
          <div>
            <p className="text-muted-foreground">Business days</p>
            <p className="font-medium">
              {sla.elapsedBusinessDays ?? 0} / {sla.totalBusinessDays}
            </p>
          </div>
        )}
        {sla.label && (
          <span className="rounded-full border px-2 py-0.5 text-xs font-medium">{sla.label}</span>
        )}
      </CardContent>
    </Card>
  );
}
