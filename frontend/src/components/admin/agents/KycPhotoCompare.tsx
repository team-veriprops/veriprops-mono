"use client";

import { ResizableSplit } from "@components/ui/ResizableSplit";
import { humanizeEnumLabel } from "@lib/utils";
import { KycRecordView } from "@/types/agent";

function Photo({ src, caption, testId }: { src: string; caption: string; testId: string }) {
  return (
    <figure className="flex h-full flex-col bg-muted/30">
      {/* eslint-disable-next-line @next/next/no-img-element -- a short-lived signed URL, not an optimisable asset */}
      <img src={src} alt={caption} data-testid={testId} className="h-72 w-full object-contain sm:h-96" />
      <figcaption className="border-t px-2 py-1 text-center text-xs text-muted-foreground">{caption}</figcaption>
    </figure>
  );
}

/**
 * The applicant's selfie beside the photo of their ID document, for a reviewer to compare
 * (§3.1). The divider drags from the centre to enlarge either side. Where no document photo
 * was needed (BVN, NIN — matched to the photo on file by the provider) the selfie shows alone.
 * The images come through short-lived links, so a stale drawer is reopened, not cached.
 */
export function KycPhotoCompare({ kyc }: { kyc: KycRecordView }) {
  if (!kyc.selfieUrl) {
    return <p className="text-sm text-muted-foreground" data-testid="admin-kyc-no-photos">No photos were kept for this check.</p>;
  }
  const selfie = <Photo src={kyc.selfieUrl} caption="Selfie" testId="admin-kyc-selfie" />;
  if (!kyc.documentUrl) {
    return <div className="overflow-hidden rounded-lg border">{selfie}</div>;
  }
  const documentName = kyc.idType ? humanizeEnumLabel(kyc.idType) : "ID document";
  return (
    <ResizableSplit
      left={selfie}
      right={<Photo src={kyc.documentUrl} caption={documentName} testId="admin-kyc-document" />}
      label={`Resize selfie and ${documentName.toLowerCase()}`}
      testId="admin-kyc-compare"
    />
  );
}
