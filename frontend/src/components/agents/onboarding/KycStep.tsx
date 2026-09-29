"use client";

import { Fingerprint, IdCard, ShieldCheck } from "lucide-react";
import { GovIdType, KycMethod } from "@/types/agent";
import { Input } from "@3rdparty/ui/input";
import { Label } from "@3rdparty/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@3rdparty/ui/select";
import { SelectableCard } from "@components/ui/SelectableCard";
import { CameraFacing, PhotoCapture } from "@components/ui/PhotoCapture";
import { AgentWizardState, KycPhotos } from "./types";
import { kycNeedsDocument } from "./validation";

interface Props {
  value: AgentWizardState["kyc"];
  onChange: (kyc: AgentWizardState["kyc"]) => void;
  photos: KycPhotos;
  onPhotosChange: (photos: KycPhotos) => void;
  /** The ID types a reviewer checks from a photo of the document (backend public config). */
  documentIdTypes: GovIdType[];
}

const ID_LABELS: Record<GovIdType, string> = {
  [GovIdType.NIN]: "NIN",
  [GovIdType.PASSPORT]: "International Passport",
  [GovIdType.DRIVERS_LICENCE]: "Driver's Licence",
  [GovIdType.VOTERS_CARD]: "Voter's Card",
};

const METHODS: { method: KycMethod; title: string; blurb: string; icon: typeof Fingerprint; testId: string; badge?: string }[] = [
  {
    method: KycMethod.BVN,
    title: "BVN",
    blurb: "Fastest — liveness & face-match via our partner",
    icon: Fingerprint,
    testId: "agent-apply-kyc-method-bvn",
    badge: "Recommended",
  },
  {
    method: KycMethod.GOV_ID,
    title: "Government ID",
    blurb: "NIN, passport, driver's licence, or voter's card",
    icon: IdCard,
    testId: "agent-apply-kyc-method-govid",
  },
];

export default function KycStep({ value, onChange, photos, onPhotosChange, documentIdTypes }: Props) {
  const set = (patch: Partial<AgentWizardState["kyc"]>) => onChange({ ...value, ...patch });
  const needsDocument = kycNeedsDocument(value, documentIdTypes);

  return (
    <div className="space-y-6" data-testid="agent-apply-kyc">
      <p className="text-sm text-muted-foreground">
        Verify your identity so customers can trust your inspections. Choose a method below.
      </p>

      {/* Method choice — selectable cards (single-select, radio semantics). */}
      <div className="grid gap-3 sm:grid-cols-2">
        {METHODS.map(({ method, title, blurb, icon, testId, badge }) => (
          <SelectableCard
            key={method}
            selectionMode="radio"
            selected={value.method === method}
            onSelect={() => set({ method })}
            icon={icon}
            title={title}
            description={blurb}
            testId={testId}
            badge={
              badge && (
                <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                  {badge}
                </span>
              )
            }
          />
        ))}
      </div>

      {value.method === KycMethod.BVN ? (
        <div className="space-y-2">
          <Label htmlFor="bvn">BVN</Label>
          <Input
            id="bvn"
            inputMode="numeric"
            maxLength={11}
            value={value.bvn ?? ""}
            onChange={(e) => set({ bvn: e.target.value })}
            placeholder="11-digit BVN"
            data-testid="agent-apply-bvn"
          />
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label>ID type</Label>
            <Select value={value.idType} onValueChange={(v) => set({ idType: v as GovIdType })}>
              {/* A Radix trigger is a <button> with no text of its own until a value is chosen,
                  so it carries the name (axe `button-name`). */}
              <SelectTrigger aria-label="ID type" data-testid="agent-apply-idtype">
                <SelectValue placeholder="Select ID type" />
              </SelectTrigger>
              <SelectContent>
                {(Object.keys(ID_LABELS) as GovIdType[]).map((t) => (
                  <SelectItem key={t} value={t}>
                    {ID_LABELS[t]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="idNumber">ID number</Label>
            <Input
              id="idNumber"
              value={value.idNumber ?? ""}
              onChange={(e) => set({ idNumber: e.target.value })}
              data-testid="agent-apply-idnumber"
            />
          </div>
        </div>
      )}

      {/* The selfie is checked for liveness and, for BVN and NIN, against the photo on file. */}
      <PhotoCapture
        label="Selfie"
        hint="Face the camera in good light, with nothing covering your face."
        facing={CameraFacing.USER}
        value={photos.selfie}
        onChange={(selfie) => onPhotosChange({ ...photos, selfie })}
        testId="agent-apply-selfie"
      />

      {needsDocument && (
        <PhotoCapture
          label={`Photo of your ${value.idType ? ID_LABELS[value.idType] : "ID"}`}
          hint="The photo page, flat and fully in frame. A reviewer compares it with your selfie."
          facing={CameraFacing.ENVIRONMENT}
          value={photos.idDocument}
          onChange={(idDocument) => onPhotosChange({ ...photos, idDocument })}
          testId="agent-apply-id-document"
        />
      )}

      {/* What happens to the photos — they are not part of a saved draft. */}
      <div className="flex items-start gap-2.5 rounded-lg bg-muted/50 p-3 text-xs text-muted-foreground">
        <ShieldCheck className="mt-0.5 size-4 shrink-0 text-emerald-600 dark:text-emerald-400" />
        <span>
          Your photos are sent securely to check your identity and kept privately for the reviewer of your
          application. They aren&apos;t saved with your progress, so if you come back later you&apos;ll take them again.
        </span>
      </div>
    </div>
  );
}
