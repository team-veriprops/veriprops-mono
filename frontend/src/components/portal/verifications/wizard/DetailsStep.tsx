"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp, AlertCircle } from "lucide-react";
import { Button } from "@3rdparty/ui/button";
import { Input } from "@3rdparty/ui/input";
import type { PropertyType } from "../libs/verification-service";

export interface DetailsStepValues {
  details: Record<string, unknown>;
  sellerInfo: {
    name?: string;
    phone?: string;
    email?: string;
    relationship?: string;
  };
  estimatedPriceMinor?: number;
  estimatedPriceCurrency?: string;
}

interface Props {
  propertyType: PropertyType;
  defaultValues?: Partial<DetailsStepValues>;
  pending?: boolean;
  onBack: () => void;
  onSubmit: (values: DetailsStepValues) => void;
}

function CollapsibleSection({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div
      className="rounded-xl overflow-hidden"
      style={{ border: "1px solid rgba(196,198,207,0.2)" }}
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-3 text-left text-sm font-semibold transition-colors hover:bg-gray-50"
        style={{ color: "var(--brand-navy)" }}
      >
        {label}
        {open ? (
          <ChevronUp className="w-4 h-4" style={{ color: "var(--brand-on-surface-variant)" }} />
        ) : (
          <ChevronDown className="w-4 h-4" style={{ color: "var(--brand-on-surface-variant)" }} />
        )}
      </button>
      {open && (
        <div className="px-4 pb-4 pt-1 space-y-3" style={{ borderTop: "1px solid rgba(196,198,207,0.1)" }}>
          {children}
        </div>
      )}
    </div>
  );
}

function SelectField({
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

export default function DetailsStep({ propertyType, defaultValues, pending, onBack, onSubmit }: Props) {
  // Land fields
  const [size, setSize] = useState(String((defaultValues?.details as any)?.size ?? ""));
  const [coStatus, setCoStatus] = useState(String((defaultValues?.details as any)?.cOfOStatus ?? "UNKNOWN"));
  // Building fields
  const [floors, setFloors] = useState(String((defaultValues?.details as any)?.floors ?? ""));
  const [age, setAge] = useState(String((defaultValues?.details as any)?.age ?? ""));
  const [occupancy, setOccupancy] = useState(String((defaultValues?.details as any)?.occupancy ?? "UNKNOWN"));

  // Estimated price
  const [estimatedPriceNgn, setEstimatedPriceNgn] = useState(
    defaultValues?.estimatedPriceMinor != null
      ? String(defaultValues.estimatedPriceMinor / 100)
      : "",
  );

  // Seller info (collapsible)
  const [sellerName, setSellerName] = useState(defaultValues?.sellerInfo?.name ?? "");
  const [sellerPhone, setSellerPhone] = useState(defaultValues?.sellerInfo?.phone ?? "");
  const [sellerEmail, setSellerEmail] = useState(defaultValues?.sellerInfo?.email ?? "");
  const [sellerRel, setSellerRel] = useState(defaultValues?.sellerInfo?.relationship ?? "");

  const [error, setError] = useState<string | null>(null);

  function handleSubmit() {
    setError(null);
    const details: Record<string, unknown> =
      propertyType === "LAND"
        ? { size: size || null, cOfOStatus: coStatus, surveyPlanStatus: "UNKNOWN" }
        : { floors: floors || null, age: age || null, occupancy, cOfOStatus: coStatus };

    const priceNum = estimatedPriceNgn ? parseFloat(estimatedPriceNgn.replace(/,/g, "")) : NaN;
    const estimatedPriceMinor = !isNaN(priceNum) && priceNum > 0
      ? Math.round(priceNum * 100)
      : undefined;

    onSubmit({
      details,
      sellerInfo: {
        name: sellerName || undefined,
        phone: sellerPhone || undefined,
        email: sellerEmail || undefined,
        relationship: sellerRel || undefined,
      },
      estimatedPriceMinor,
      estimatedPriceCurrency: estimatedPriceMinor ? "NGN" : undefined,
    });
  }

  return (
    <div className="space-y-6">
      <div>
        <h2
          className="text-2xl font-semibold tracking-tight"
          style={{ color: "var(--brand-navy)", fontFamily: "var(--font-display, Manrope)" }}
        >
          Property details
        </h2>
        <p className="text-sm mt-1" style={{ color: "var(--brand-on-surface-variant)" }}>
          Tell us what you know. Anything you don&apos;t know our agents will uncover.
        </p>
      </div>

      {/* Type-specific fields */}
      <div className="space-y-3">
        <h3 className="text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--brand-viridian)" }}>
          {propertyType === "LAND" ? "Land details" : "Building details"}
        </h3>
        {propertyType === "LAND" ? (
          <div className="grid sm:grid-cols-2 gap-3">
            <Input
              placeholder="Size (sqm or plots)"
              value={size}
              onChange={(e) => setSize(e.target.value)}
            />
            <SelectField
              value={coStatus}
              onChange={setCoStatus}
              options={[
                { value: "UNKNOWN", label: "C of O — Unknown" },
                { value: "OBTAINED", label: "C of O obtained" },
                { value: "PENDING", label: "C of O pending" },
                { value: "NONE", label: "No C of O" },
              ]}
            />
          </div>
        ) : (
          <div className="space-y-3">
            <div className="grid sm:grid-cols-3 gap-3">
              <Input placeholder="Floors" value={floors} onChange={(e) => setFloors(e.target.value)} />
              <Input placeholder="Age (years)" value={age} onChange={(e) => setAge(e.target.value)} />
              <SelectField
                value={occupancy}
                onChange={setOccupancy}
                options={[
                  { value: "UNKNOWN", label: "Occupancy — Unknown" },
                  { value: "OCCUPIED", label: "Occupied" },
                  { value: "VACANT", label: "Vacant" },
                ]}
              />
            </div>
            <SelectField
              value={coStatus}
              onChange={setCoStatus}
              options={[
                { value: "UNKNOWN", label: "C of O — Unknown" },
                { value: "OBTAINED", label: "C of O obtained" },
                { value: "PENDING", label: "C of O pending" },
                { value: "NONE", label: "No C of O" },
              ]}
            />
          </div>
        )}
      </div>

      {/* Estimated price */}
      <div className="space-y-2">
        <h3 className="text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--brand-viridian)" }}>
          Estimated market value (optional)
        </h3>
        <div className="flex items-center gap-2">
          <span className="text-sm font-bold flex-shrink-0" style={{ color: "var(--brand-on-surface-variant)" }}>
            ₦
          </span>
          <Input
            type="number"
            placeholder="0"
            value={estimatedPriceNgn}
            onChange={(e) => setEstimatedPriceNgn(e.target.value)}
            className="flex-1"
          />
        </div>
        <p className="text-xs" style={{ color: "var(--brand-on-surface-variant)" }}>
          This helps us understand the market — not shared publicly or used in your report.
        </p>
      </div>

      {/* Seller info — collapsible */}
      <CollapsibleSection label="Add seller info (optional)">
        <div className="grid sm:grid-cols-2 gap-3">
          <Input placeholder="Seller name" value={sellerName} onChange={(e) => setSellerName(e.target.value)} />
          <Input placeholder="Phone" value={sellerPhone} onChange={(e) => setSellerPhone(e.target.value)} />
          <Input placeholder="Email" value={sellerEmail} onChange={(e) => setSellerEmail(e.target.value)} />
          <Input
            placeholder="Relationship (agent / direct / other)"
            value={sellerRel}
            onChange={(e) => setSellerRel(e.target.value)}
          />
        </div>
      </CollapsibleSection>

      {error && (
        <div
          className="flex items-start gap-2 text-sm rounded-md p-3"
          style={{ color: "var(--destructive)", backgroundColor: "rgba(186,26,26,0.06)" }}
        >
          <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <div className="flex justify-between pt-2">
        <Button type="button" variant="outline" onClick={onBack}>
          Back
        </Button>
        <Button type="button" disabled={pending} onClick={handleSubmit}>
          {pending ? "Saving…" : "Continue to pricing"}
        </Button>
      </div>
    </div>
  );
}
