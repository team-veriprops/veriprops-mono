"use client";

import { GovIdType, KycMethod } from "@/types/agent";
import { Input } from "@3rdparty/ui/input";
import { Label } from "@3rdparty/ui/label";
import { RadioGroup, RadioGroupItem } from "@3rdparty/ui/radio-group";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@3rdparty/ui/select";
import { AgentWizardState } from "./types";

interface Props {
  value: AgentWizardState["kyc"];
  onChange: (kyc: AgentWizardState["kyc"]) => void;
}

const ID_LABELS: Record<GovIdType, string> = {
  [GovIdType.NIN]: "NIN",
  [GovIdType.PASSPORT]: "International Passport",
  [GovIdType.DRIVERS_LICENCE]: "Driver's Licence",
  [GovIdType.VOTERS_CARD]: "Voter's Card",
};

export default function KycStep({ value, onChange }: Props) {
  const set = (patch: Partial<AgentWizardState["kyc"]>) => onChange({ ...value, ...patch });

  return (
    <div className="space-y-6" data-testid="agent-apply-kyc">
      <p className="text-sm text-muted-foreground">
        Verify your identity. BVN is the primary method (liveness &amp; face-match are handled by our
        verification partner); a government ID is the fallback. We store only the verification result — never
        raw biometric data.
      </p>

      <RadioGroup
        value={value.method}
        onValueChange={(v) => set({ method: v as KycMethod })}
        className="flex gap-6"
      >
        <label className="flex items-center gap-2">
          <RadioGroupItem value={KycMethod.BVN} data-testid="agent-apply-kyc-method-bvn" /> BVN (recommended)
        </label>
        <label className="flex items-center gap-2">
          <RadioGroupItem value={KycMethod.GOV_ID} data-testid="agent-apply-kyc-method-govid" /> Government ID
        </label>
      </RadioGroup>

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
              <SelectTrigger data-testid="agent-apply-idtype">
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
    </div>
  );
}
