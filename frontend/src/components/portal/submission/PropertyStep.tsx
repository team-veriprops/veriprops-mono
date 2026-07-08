"use client";

import { useState } from "react";
import { Building2, LandPlot, MapPin } from "lucide-react";
import { Input } from "@3rdparty/ui/input";
import { Label } from "@3rdparty/ui/label";
import { PropertyKind } from "@/types/verification";
import { useGeoAutocompleteQuery } from "@components/portal/libs/useVerificationQueries";
import { useDebounce } from "@hooks/useDebounce";
import { cn } from "@lib/utils";
import { SubmissionState } from "./types";

interface Props {
  value: SubmissionState["property"];
  onChange: (patch: Partial<SubmissionState["property"]>) => void;
}

const PROPERTY_TYPES = [
  { kind: PropertyKind.LAND, title: "Land", blurb: "A plot, parcel, or bare land", icon: LandPlot },
  { kind: PropertyKind.BUILDING, title: "Building", blurb: "A house, flat, or developed structure", icon: Building2 },
] as const;

// Conditional facts the agent confirms on the ground (PRD §5.1). Kept lightweight — a
// select or two per type; free-text where the answer varies. Stored under property.details.
const LAND_USE = ["Residential", "Commercial", "Mixed use", "Agricultural"];
const SURVEY_STATUS = ["Survey plan available", "No survey plan", "Not sure"];
const BUILDING_TYPES = ["Bungalow", "Duplex", "Block of flats", "Commercial", "Other"];
const OCCUPANCY = ["Occupied", "Vacant", "Under construction"];

export default function PropertyStep({ value, onChange }: Props) {
  const [addressInput, setAddressInput] = useState(value.address);
  const debounced = useDebounce(addressInput, 300);
  const { data: suggestions = [] } = useGeoAutocompleteQuery(debounced);
  const isLand = value.propertyType === PropertyKind.LAND;

  const setDetail = (key: string, v: string) =>
    onChange({ details: { ...value.details, [key]: v } });

  return (
    <div className="space-y-8" data-testid="verify-new-property">
      {/* Property type — large selectable cards (mobile-first tap targets). */}
      <fieldset className="space-y-3">
        <legend className="text-sm font-medium text-foreground">What are you verifying?</legend>
        <div className="grid gap-3 sm:grid-cols-2">
          {PROPERTY_TYPES.map(({ kind, title, blurb, icon: Icon }) => {
            const selected = value.propertyType === kind;
            return (
              <button
                key={kind}
                type="button"
                aria-pressed={selected}
                onClick={() => onChange({ propertyType: kind })}
                className={cn(
                  "flex items-start gap-3 rounded-xl border p-4 text-left transition-all",
                  selected
                    ? "border-primary bg-primary/5 ring-1 ring-primary"
                    : "border-border hover:border-primary/40 hover:bg-accent",
                )}
                data-testid={`verify-new-type-${kind.toLowerCase()}`}
              >
                <span
                  className={cn(
                    "flex size-10 shrink-0 items-center justify-center rounded-lg",
                    selected ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground",
                  )}
                >
                  <Icon className="size-5" />
                </span>
                <span className="min-w-0">
                  <span className="block font-semibold text-foreground">{title}</span>
                  <span className="block text-sm text-muted-foreground">{blurb}</span>
                </span>
              </button>
            );
          })}
        </div>
      </fieldset>

      {/* Address with geo-autocomplete. */}
      <div className="space-y-2">
        <Label htmlFor="address">Property address</Label>
        <div className="relative">
          <MapPin className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            id="address"
            value={addressInput}
            onChange={(e) => {
              setAddressInput(e.target.value);
              onChange({ address: e.target.value, placeId: undefined });
            }}
            placeholder="Start typing the property address"
            data-testid="verify-new-address"
            autoComplete="off"
            className="pl-9"
          />
          {suggestions.length > 0 && addressInput !== value.address && (
            <ul className="absolute z-10 mt-1 w-full overflow-hidden rounded-lg border border-border bg-popover shadow-md">
              {suggestions.map((s) => (
                <li key={s.placeId}>
                  <button
                    type="button"
                    className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-accent"
                    onClick={() => {
                      setAddressInput(s.description);
                      onChange({ address: s.description, placeId: s.placeId });
                    }}
                  >
                    <MapPin className="size-3.5 shrink-0 text-muted-foreground" />
                    <span className="truncate">{s.description}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
        {value.placeId && (
          <p className="text-xs text-emerald-600 dark:text-emerald-400">✓ Location matched on the map</p>
        )}
      </div>

      {/* Landmark — the mandatory escape valve for informal plots (§5.1 1C). */}
      <div className="space-y-2">
        <Label htmlFor="landmark">Nearest junction, landmark, or local description</Label>
        <Input
          id="landmark"
          value={value.landmark}
          onChange={(e) => onChange({ landmark: e.target.value })}
          placeholder="e.g. Opposite Zenith Bank, off Admiralty Way"
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

      {/* Conditional detail fields (PRD §5.1) — what the agent should confirm. Optional, but
          they sharpen the brief. */}
      <fieldset className="space-y-4 rounded-xl border border-dashed border-border p-4">
        <legend className="px-1 text-sm font-medium text-foreground">
          {isLand ? "About the land" : "About the building"}
          <span className="ml-1 font-normal text-muted-foreground">(optional)</span>
        </legend>
        {isLand ? (
          <div className="grid gap-4 sm:grid-cols-2">
            <DetailSelect label="Intended use" options={LAND_USE}
              value={value.details.landUse} onChange={(v) => setDetail("landUse", v)}
              testId="verify-new-land-use" />
            <DetailSelect label="Survey status" options={SURVEY_STATUS}
              value={value.details.surveyStatus} onChange={(v) => setDetail("surveyStatus", v)}
              testId="verify-new-survey-status" />
            <DetailText label="Approx. size" placeholder="e.g. 600 sqm / 1 plot"
              value={value.details.size} onChange={(v) => setDetail("size", v)}
              testId="verify-new-land-size" />
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2">
            <DetailSelect label="Building type" options={BUILDING_TYPES}
              value={value.details.buildingType} onChange={(v) => setDetail("buildingType", v)}
              testId="verify-new-building-type" />
            <DetailSelect label="Occupancy" options={OCCUPANCY}
              value={value.details.occupancy} onChange={(v) => setDetail("occupancy", v)}
              testId="verify-new-occupancy" />
            <DetailText label="Number of floors" placeholder="e.g. 2" inputMode="numeric"
              value={value.details.floors} onChange={(v) => setDetail("floors", v)}
              testId="verify-new-floors" />
            <DetailText label="Year built (approx.)" placeholder="e.g. 2018"
              value={value.details.yearBuilt} onChange={(v) => setDetail("yearBuilt", v)}
              testId="verify-new-year-built" />
          </div>
        )}
      </fieldset>
    </div>
  );
}

function DetailText({ label, value, onChange, placeholder, testId, inputMode }: {
  label: string; value?: string; onChange: (v: string) => void;
  placeholder?: string; testId: string; inputMode?: "numeric" | "text";
}) {
  return (
    <div className="space-y-1.5">
      <Label className="text-xs">{label}</Label>
      <Input value={value ?? ""} onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder} inputMode={inputMode} data-testid={testId} />
    </div>
  );
}

function DetailSelect({ label, options, value, onChange, testId }: {
  label: string; options: string[]; value?: string; onChange: (v: string) => void; testId: string;
}) {
  return (
    <div className="space-y-1.5">
      <Label className="text-xs">{label}</Label>
      <select
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value)}
        data-testid={testId}
        className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
      >
        <option value="">Select…</option>
        {options.map((o) => (
          <option key={o} value={o}>{o}</option>
        ))}
      </select>
    </div>
  );
}
