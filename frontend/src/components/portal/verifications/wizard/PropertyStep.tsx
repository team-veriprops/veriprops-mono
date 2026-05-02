"use client";

import { useState } from "react";
import { Button } from "@3rdparty/ui/button";
import { Input } from "@3rdparty/ui/input";
import { MapPin, AlertCircle } from "lucide-react";
import { nigerianStates, getLgasForState } from "@lib/nigerianLocations";
import type { PropertyType } from "../libs/verification-service";

export interface PropertyStepValues {
  source: "MANUAL" | "LISTING_URL";
  sourceUrl?: string;
  propertyType: PropertyType;
  state: string;
  lga?: string;
  addressLine?: string;
  landmarkDescription?: string;
  details: Record<string, unknown>;
  sellerInfo: {
    name?: string;
    phone?: string;
    email?: string;
    relationship?: string;
  };
}

interface Props {
  defaultValues?: Partial<PropertyStepValues>;
  pending?: boolean;
  onSubmit: (values: PropertyStepValues) => void;
}

const stateLabel = new Map(nigerianStates.map((s) => [s.value, s.label]));

function normaliseState(value: string): string {
  return value.replace(/-/g, "_").toUpperCase();
}

export default function PropertyStep({ defaultValues, pending, onSubmit }: Props) {
  const [source, setSource] = useState<"MANUAL" | "LISTING_URL">(
    defaultValues?.source ?? "MANUAL",
  );
  const [sourceUrl, setSourceUrl] = useState(defaultValues?.sourceUrl ?? "");
  const [propertyType, setPropertyType] = useState<PropertyType>(
    defaultValues?.propertyType ?? "LAND",
  );
  const [stateValue, setStateValue] = useState(defaultValues?.state?.toLowerCase().replace(/_/g, "-") ?? "lagos");
  const [lga, setLga] = useState(defaultValues?.lga ?? "");
  const [addressLine, setAddressLine] = useState(defaultValues?.addressLine ?? "");
  const [landmark, setLandmark] = useState(defaultValues?.landmarkDescription ?? "");

  // Type-specific fields
  const [size, setSize] = useState<string>(String((defaultValues?.details as any)?.size ?? ""));
  const [coStatus, setCoStatus] = useState<string>(
    String((defaultValues?.details as any)?.cOfOStatus ?? "UNKNOWN"),
  );
  const [floors, setFloors] = useState<string>(String((defaultValues?.details as any)?.floors ?? ""));
  const [age, setAge] = useState<string>(String((defaultValues?.details as any)?.age ?? ""));
  const [occupancy, setOccupancy] = useState<string>(
    String((defaultValues?.details as any)?.occupancy ?? "UNKNOWN"),
  );

  const [sellerName, setSellerName] = useState<string>(defaultValues?.sellerInfo?.name ?? "");
  const [sellerPhone, setSellerPhone] = useState<string>(defaultValues?.sellerInfo?.phone ?? "");
  const [sellerEmail, setSellerEmail] = useState<string>(defaultValues?.sellerInfo?.email ?? "");
  const [sellerRel, setSellerRel] = useState<string>(defaultValues?.sellerInfo?.relationship ?? "");
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = () => {
    setError(null);
    if (!stateValue) {
      setError("Select the property state.");
      return;
    }
    if (!landmark || landmark.length < 5) {
      setError(
        "A short landmark description is required — 'nearest junction, landmark, or local description'.",
      );
      return;
    }
    const details: Record<string, unknown> =
      propertyType === "LAND"
        ? { size: size || null, cOfOStatus: coStatus, surveyPlanStatus: "UNKNOWN" }
        : { floors: floors || null, age: age || null, occupancy, cOfOStatus: coStatus };

    onSubmit({
      source,
      sourceUrl: source === "LISTING_URL" ? sourceUrl : undefined,
      propertyType,
      state: normaliseState(stateValue),
      lga: lga || undefined,
      addressLine: addressLine || undefined,
      landmarkDescription: landmark,
      details,
      sellerInfo: {
        name: sellerName || undefined,
        phone: sellerPhone || undefined,
        email: sellerEmail || undefined,
        relationship: sellerRel || undefined,
      },
    });
  };

  return (
    <div className="space-y-6">
      <div>
        <h2
          className="text-2xl font-semibold tracking-tight"
          style={{ color: "var(--brand-navy)", fontFamily: "var(--font-display, Manrope)" }}
        >
          Tell us about the property
        </h2>
        <p className="text-sm mt-1" style={{ color: "var(--brand-on-surface-variant)" }}>
          Add as much detail as you can. Anything you don&apos;t know we&apos;ll uncover during verification.
        </p>
      </div>

      <Section title="Source">
        <div className="grid grid-cols-2 gap-2">
          <Pill active={source === "MANUAL"} onClick={() => setSource("MANUAL")}>
            Enter manually
          </Pill>
          <Pill active={source === "LISTING_URL"} onClick={() => setSource("LISTING_URL")}>
            Paste listing URL
          </Pill>
        </div>
        {source === "LISTING_URL" && (
          <Input
            placeholder="https://nigeriapropertycentre.com/…"
            value={sourceUrl}
            onChange={(e) => setSourceUrl(e.target.value)}
          />
        )}
      </Section>

      <Section title="Property type">
        <div className="grid grid-cols-2 gap-2">
          <Pill active={propertyType === "LAND"} onClick={() => setPropertyType("LAND")}>
            Land
          </Pill>
          <Pill active={propertyType === "BUILDING"} onClick={() => setPropertyType("BUILDING")}>
            Building
          </Pill>
        </div>
      </Section>

      <Section title="Location">
        <div className="grid sm:grid-cols-2 gap-3">
          <label>
            <span
              className="text-xs font-medium block mb-1.5"
              style={{ color: "var(--brand-on-surface-variant)" }}
            >
              State
            </span>
            <select
              value={stateValue}
              onChange={(e) => {
                setStateValue(e.target.value);
                setLga("");
              }}
              className="w-full rounded-md py-2.5 px-3 text-sm"
              style={{
                backgroundColor: "var(--brand-surface-card)",
                color: "var(--brand-navy)",
                border: "1px solid var(--border)",
              }}
            >
              {nigerianStates.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span
              className="text-xs font-medium block mb-1.5"
              style={{ color: "var(--brand-on-surface-variant)" }}
            >
              LGA
            </span>
            <select
              value={lga}
              onChange={(e) => setLga(e.target.value)}
              className="w-full rounded-md py-2.5 px-3 text-sm"
              style={{
                backgroundColor: "var(--brand-surface-card)",
                color: "var(--brand-navy)",
                border: "1px solid var(--border)",
              }}
            >
              <option value="">—</option>
              {getLgasForState(stateValue).map((l) => (
                <option key={l.value} value={l.value}>
                  {l.label}
                </option>
              ))}
            </select>
          </label>
        </div>
        <Input
          placeholder="Street address (optional)"
          value={addressLine}
          onChange={(e) => setAddressLine(e.target.value)}
        />
        <div>
          <div
            className="text-xs font-medium mb-1.5 flex items-center gap-1.5"
            style={{ color: "var(--brand-on-surface-variant)" }}
          >
            <MapPin className="w-3 h-3" />
            Nearest junction, landmark, or local description (required)
          </div>
          <textarea
            rows={3}
            className="w-full rounded-md p-3 text-sm"
            style={{
              backgroundColor: "var(--brand-surface-card)",
              border: "1px solid var(--border)",
              color: "var(--brand-navy)",
            }}
            value={landmark}
            onChange={(e) => setLandmark(e.target.value)}
            placeholder="e.g. Two streets after Mobil filling station, opposite Mama Cherry's"
          />
        </div>
      </Section>

      {propertyType === "LAND" ? (
        <Section title="Land details">
          <div className="grid sm:grid-cols-2 gap-3">
            <Input
              placeholder="Size (sqm or plots)"
              value={size}
              onChange={(e) => setSize(e.target.value)}
            />
            <Select
              value={coStatus}
              onChange={setCoStatus}
              options={[
                { value: "UNKNOWN", label: "C of O status — Unknown" },
                { value: "OBTAINED", label: "C of O obtained" },
                { value: "PENDING", label: "C of O pending" },
                { value: "NONE", label: "No C of O" },
              ]}
            />
          </div>
        </Section>
      ) : (
        <Section title="Building details">
          <div className="grid sm:grid-cols-3 gap-3">
            <Input placeholder="Floors" value={floors} onChange={(e) => setFloors(e.target.value)} />
            <Input placeholder="Age (years)" value={age} onChange={(e) => setAge(e.target.value)} />
            <Select
              value={occupancy}
              onChange={setOccupancy}
              options={[
                { value: "UNKNOWN", label: "Occupancy — Unknown" },
                { value: "OCCUPIED", label: "Occupied" },
                { value: "VACANT", label: "Vacant" },
              ]}
            />
          </div>
          <Select
            value={coStatus}
            onChange={setCoStatus}
            options={[
              { value: "UNKNOWN", label: "C of O status — Unknown" },
              { value: "OBTAINED", label: "C of O obtained" },
              { value: "PENDING", label: "C of O pending" },
              { value: "NONE", label: "No C of O" },
            ]}
          />
        </Section>
      )}

      <Section title="Seller info (optional)">
        <div className="grid sm:grid-cols-2 gap-3">
          <Input
            placeholder="Seller name"
            value={sellerName}
            onChange={(e) => setSellerName(e.target.value)}
          />
          <Input
            placeholder="Phone"
            value={sellerPhone}
            onChange={(e) => setSellerPhone(e.target.value)}
          />
          <Input
            placeholder="Email"
            value={sellerEmail}
            onChange={(e) => setSellerEmail(e.target.value)}
          />
          <Input
            placeholder="Relationship (agent / direct / other)"
            value={sellerRel}
            onChange={(e) => setSellerRel(e.target.value)}
          />
        </div>
      </Section>

      {error && (
        <div
          className="flex items-start gap-2 text-sm rounded-md p-3"
          style={{
            color: "var(--destructive)",
            backgroundColor: "rgba(186,26,26,0.06)",
          }}
        >
          <AlertCircle className="w-4 h-4 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      <div className="flex justify-end pt-2">
        <Button type="button" disabled={pending} onClick={handleSubmit}>
          {pending ? "Saving…" : "Continue to pricing"}
        </Button>
      </div>
    </div>
  );
}

function Pill({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="text-sm font-medium rounded-md py-2.5 transition-colors"
      style={{
        backgroundColor: active ? "var(--brand-viridian)" : "var(--brand-surface-low)",
        color: active ? "white" : "var(--brand-on-surface)",
      }}
    >
      {children}
    </button>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3
        className="text-xs font-semibold uppercase tracking-wider mb-2"
        style={{ color: "var(--brand-viridian)" }}
      >
        {title}
      </h3>
      <div className="space-y-3">{children}</div>
    </div>
  );
}

function Select({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="w-full rounded-md py-2.5 px-3 text-sm"
      style={{
        backgroundColor: "var(--brand-surface-card)",
        color: "var(--brand-navy)",
        border: "1px solid var(--border)",
      }}
    >
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );
}
