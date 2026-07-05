"use client";

import { useState } from "react";
import { FileText, ImageIcon, ShieldCheck, Video } from "lucide-react";
import DetailDrawer, { DetailDrawerWidth } from "@components/ui/DetailDrawer";
import { EvidenceKind } from "@/types/agentTask";
import { CustomerEvidence } from "@/types/tracking";
import { cn } from "@lib/utils";

const KIND_ICON: Record<string, typeof ImageIcon> = {
  [EvidenceKind.PHOTO]: ImageIcon,
  [EvidenceKind.VIDEO]: Video,
  [EvidenceKind.DOCUMENT]: FileText,
  [EvidenceKind.SIGNATURE]: FileText,
  [EvidenceKind.CERTIFICATE]: FileText,
};

const isRenderableImage = (e: CustomerEvidence) =>
  e.kind === EvidenceKind.PHOTO && !!e.url && e.url.startsWith("http");

/**
 * Read-only evidence gallery (§9.4). Each item is tagged by role (never agent name),
 * carries a content hash + server GPS/timestamp, and opens a full-screen viewer with a
 * tamper-evidence metadata panel. Progressive/derivative image loading is a documented
 * follow-up — the full-resolution original is served for now.
 */
export function EvidenceGallery({ items }: { items: CustomerEvidence[] }) {
  const [active, setActive] = useState<CustomerEvidence | null>(null);

  return (
    <>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {items.map((e) => {
          const Icon = KIND_ICON[e.kind] ?? FileText;
          return (
            <button
              key={e.id}
              type="button"
              onClick={() => setActive(e)}
              className="group flex aspect-square flex-col items-center justify-center gap-2 overflow-hidden rounded-lg border bg-muted/30 p-2 text-center transition hover:border-primary"
            >
              {isRenderableImage(e) ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={e.url} alt={`${e.role} evidence`} className="h-full w-full object-cover" />
              ) : (
                <Icon className="size-8 text-muted-foreground" />
              )}
              <span className="text-[10px] font-medium uppercase text-muted-foreground">{e.role}</span>
            </button>
          );
        })}
      </div>

      <DetailDrawer
        open={!!active}
        onOpenChange={(o) => !o && setActive(null)}
        title={active ? `${active.role} · ${active.kind}` : "Evidence"}
        reference={active?.contentSha256 ?? ""}
        drawerWidth={DetailDrawerWidth.SMALL}
      >
        {active && <EvidenceViewer evidence={active} />}
      </DetailDrawer>
    </>
  );
}

function EvidenceViewer({ evidence: e }: { evidence: CustomerEvidence }) {
  return (
    <div className="space-y-4 p-6" data-testid="evidence-viewer">
      {isRenderableImage(e) ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={e.url} alt={`${e.role} evidence`} className="mx-auto max-h-[60vh] rounded-lg object-contain" />
      ) : (
        <div className="flex h-40 items-center justify-center rounded-lg bg-muted text-muted-foreground">
          Preview not available for this file type
        </div>
      )}

      <dl className="space-y-2 text-xs">
        <MetaRow label="Uploaded">{new Date(e.uploadedAt).toLocaleString()}</MetaRow>
        {e.capturedAt && <MetaRow label="Captured">{new Date(e.capturedAt).toLocaleString()}</MetaRow>}
        {e.gpsLatitude != null && e.gpsLongitude != null && (
          <MetaRow label="Location">{e.gpsLatitude.toFixed(5)}, {e.gpsLongitude.toFixed(5)}</MetaRow>
        )}
        <div className="flex items-start gap-1.5 rounded-md bg-muted/50 p-2">
          <ShieldCheck className="mt-0.5 size-3.5 shrink-0 text-primary" />
          <div className="min-w-0">
            <p className="font-medium">Tamper-evident content hash (SHA-256)</p>
            <p className={cn("truncate font-mono text-muted-foreground")} title={e.contentSha256}>
              {e.contentSha256}
            </p>
          </div>
        </div>
      </dl>
    </div>
  );
}

function MetaRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-3">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="text-right font-medium">{children}</dd>
    </div>
  );
}
