"use client";

import { Button } from "@3rdparty/ui/button";
import { Clock, CheckCircle2, XCircle } from "lucide-react";
import type { AgentApplication } from "../libs/agent-service";

interface Props {
  application: AgentApplication;
  onEdit?: () => void;
}

export default function ApprovalStatusCard({ application, onEdit }: Props) {
  if (application.status === "APPROVED") {
    return (
      <Card
        accent="var(--success)"
        accentBg="rgba(58,154,106,0.08)"
        icon={<CheckCircle2 className="w-7 h-7" />}
        title="You're an approved agent"
        body="You can now accept jobs in your coverage area. Head to your dashboard to see what's available."
        cta={{ label: "Go to dashboard", href: "/agents/dashboard" }}
      />
    );
  }
  if (application.status === "REJECTED") {
    return (
      <Card
        accent="var(--destructive)"
        accentBg="rgba(186,26,26,0.06)"
        icon={<XCircle className="w-7 h-7" />}
        title="Application not approved"
        body={
          application.rejectionReason ||
          "We couldn't approve your application. You can re-apply once the issue is addressed."
        }
        cta={onEdit ? { label: "Edit & resubmit", onClick: onEdit } : undefined}
      />
    );
  }
  return (
    <Card
      accent="var(--brand-gold)"
      accentBg="var(--brand-gold-xlight)"
      icon={<Clock className="w-7 h-7" />}
      title="Pending review"
      body="Our team typically reviews applications within 2–5 business days. We'll email you the moment a decision is made."
      cta={onEdit ? { label: "View application", onClick: onEdit } : undefined}
    />
  );
}

function Card({
  accent,
  accentBg,
  icon,
  title,
  body,
  cta,
}: {
  accent: string;
  accentBg: string;
  icon: React.ReactNode;
  title: string;
  body: string;
  cta?: { label: string; href?: string; onClick?: () => void };
}) {
  return (
    <div
      className="rounded-2xl p-8 text-center max-w-md mx-auto space-y-5"
      style={{
        backgroundColor: "var(--brand-surface-card)",
        boxShadow: "0px 24px 48px rgba(0,13,34,0.06)",
      }}
    >
      <div
        className="mx-auto w-14 h-14 rounded-full flex items-center justify-center"
        style={{ backgroundColor: accentBg, color: accent }}
      >
        {icon}
      </div>
      <div>
        <h2
          className="text-2xl font-semibold tracking-tight"
          style={{ color: "var(--brand-navy)", fontFamily: "var(--font-display, Manrope)" }}
        >
          {title}
        </h2>
        <p
          className="text-sm mt-2 leading-6"
          style={{ color: "var(--brand-on-surface-variant)" }}
        >
          {body}
        </p>
      </div>
      {cta && (
        cta.href ? (
          <Button asChild>
            <a href={cta.href}>{cta.label}</a>
          </Button>
        ) : (
          <Button type="button" onClick={cta.onClick}>
            {cta.label}
          </Button>
        )
      )}
    </div>
  );
}
