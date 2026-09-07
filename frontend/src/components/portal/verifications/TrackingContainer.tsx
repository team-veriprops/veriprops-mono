"use client";

import Link from "next/link";
import { BadgeCheck, FileText, ShieldCheck } from "lucide-react";
import { Button } from "@3rdparty/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@3rdparty/ui/card";
import { CopyText } from "@components/ui/CopyText";
import { AsyncStateComponent } from "@components/ui/AsyncStateComponent";
import { ROUTES } from "@lib/routes";
import { humanizeEnumLabel } from "@lib/utils";
import { useVerificationTracking } from "@components/portal/libs/useVerificationQueries";
import { VerificationStatus } from "@/types/verification";
import { VerificationTracking } from "@/types/tracking";
import { VerificationStatusBadge } from "./VerificationStatusBadge";
import { VerificationProgress } from "./VerificationProgress";
import { EvidenceGallery } from "./EvidenceGallery";
import WhatsAppContinueButton from "@components/portal/WhatsAppContinueButton";
import DelegatePanel from "./DelegatePanel";

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

            {t.status === VerificationStatus.COMPLETED && (
              <Card className="border-primary/40 bg-primary/5">
                <CardContent className="flex flex-wrap items-center justify-between gap-3 pt-6">
                  <div className="flex items-center gap-2 text-sm font-medium">
                    <FileText className="size-4 text-primary" /> Your report is ready.
                  </div>
                  <Button asChild size="sm">
                    <Link href={ROUTES.PORTAL.VERIFICATION_REPORT(verificationId)} data-testid="tracking-view-report">
                      View report
                    </Link>
                  </Button>
                </CardContent>
              </Card>
            )}

            <div>
              <Button asChild variant="outline" size="sm">
                <Link
                  href={ROUTES.PORTAL.VERIFICATION_MESSAGES(verificationId)}
                  data-testid="tracking-messages"
                >
                  Messages
                </Link>
              </Button>
            </div>

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
                      <span className="text-muted-foreground">· {humanizeEnumLabel(a.role)}</span>
                      {a.verified && <BadgeCheck className="size-4 text-primary" aria-label="Verified" />}
                    </div>
                  ))}
                </CardContent>
              </Card>
            )}

            {/*
              §26.4.5 — placed with the people on the case and ahead of the evidence a
              delegate must never see. The order is the grant, rendered.
            */}
            <DelegatePanel verificationId={verificationId} />

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

            <Link
              href={ROUTES.PORTAL.VERIFICATION_ACTIVITY(verificationId)}
              className="text-sm text-primary hover:underline"
              data-testid="view-activity"
            >
              View full activity history
            </Link>
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
        {t.tier && <span className="text-xs text-muted-foreground">{humanizeEnumLabel(t.tier)} tier</span>}
      </div>
      <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
        <span>Verification ID</span>
        <CopyText text={t.vid} />
        {/* §26.4.3 web→chat: the channel is only two-way if leaving for it is as easy as
            arriving from it. The link pre-fills this reference, which the bot matches. */}
        <WhatsAppContinueButton vid={t.vid} />
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
