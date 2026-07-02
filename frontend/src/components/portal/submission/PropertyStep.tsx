"use client";

import { useState } from "react";
import { Input } from "@3rdparty/ui/input";
import { Label } from "@3rdparty/ui/label";
import { RadioGroup, RadioGroupItem } from "@3rdparty/ui/radio-group";
import { PropertyKind } from "@/types/verification";
import { useGeoAutocompleteQuery } from "@components/portal/libs/useVerificationQueries";
import { useDebounce } from "@hooks/useDebounce";
import { SubmissionState } from "./types";

interface Props {
  value: SubmissionState["property"];
  onChange: (patch: Partial<SubmissionState["property"]>) => void;
}

export default function PropertyStep({ value, onChange }: Props) {
  const [addressInput, setAddressInput] = useState(value.address);
  const debounced = useDebounce(addressInput, 300);
  const { data: suggestions = [] } = useGeoAutocompleteQuery(debounced);

  return (
    <div className="space-y-6" data-testid="verify-new-property">
      <div className="space-y-2">
        <Label>Property type</Label>
        <RadioGroup
          value={value.propertyType}
          onValueChange={(v) => onChange({ propertyType: v as PropertyKind })}
          className="flex gap-6"
        >
          <label className="flex items-center gap-2">
            <RadioGroupItem value={PropertyKind.LAND} data-testid="verify-new-type-land" /> Land
          </label>
          <label className="flex items-center gap-2">
            <RadioGroupItem value={PropertyKind.BUILDING} data-testid="verify-new-type-building" /> Building
          </label>
        </RadioGroup>
      </div>

      <div className="space-y-2">
        <Label htmlFor="address">Address</Label>
        <Input
          id="address"
          value={addressInput}
          onChange={(e) => {
            setAddressInput(e.target.value);
            onChange({ address: e.target.value });
          }}
          placeholder="Start typing the property address"
          data-testid="verify-new-address"
          autoComplete="off"
        />
        {suggestions.length > 0 && addressInput !== value.address && (
          <ul className="rounded-md border border-border bg-card text-sm">
            {suggestions.map((s) => (
              <li key={s.placeId}>
                <button
                  type="button"
                  className="w-full px-3 py-2 text-left hover:bg-accent"
                  onClick={() => {
                    setAddressInput(s.description);
                    onChange({ address: s.description, placeId: s.placeId });
                  }}
                >
                  {s.description}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="space-y-2">
        <Label htmlFor="landmark">Nearest junction, landmark, or local description</Label>
        <Input
          id="landmark"
          value={value.landmark}
          onChange={(e) => onChange({ landmark: e.target.value })}
          placeholder="Help the agent find it"
          data-testid="verify-new-landmark"
        />
        <p className="text-xs text-muted-foreground">
          Google Places can miss informal plots — a landmark helps our agent locate the property.
        </p>
      </div>

      <div className="space-y-2">
        <Label htmlFor="state">State</Label>
        <Input
          id="state"
          value={value.state}
          onChange={(e) => onChange({ state: e.target.value })}
          placeholder="e.g. Lagos"
          data-testid="verify-new-state"
        />
      </div>
    </div>
  );
}
