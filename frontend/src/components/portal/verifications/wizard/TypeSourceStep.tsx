"use client";

import { useState } from "react";
import { TreePine, Building2, Link, X } from "lucide-react";
import { Input } from "@3rdparty/ui/input";
import type { PropertyType } from "../libs/verification-service";

export interface TypeSourceStepValues {
  propertyType: PropertyType;
  source: "MANUAL" | "LISTING_URL";
  sourceUrl?: string;
}

interface Props {
  defaultValues?: Partial<TypeSourceStepValues>;
  onSubmit: (values: TypeSourceStepValues) => void;
}

export default function TypeSourceStep({ defaultValues, onSubmit }: Props) {
  const [propertyType, setPropertyType] = useState<PropertyType>(
    defaultValues?.propertyType ?? "LAND",
  );
  const [showUrlInput, setShowUrlInput] = useState(
    defaultValues?.source === "LISTING_URL",
  );
  const [sourceUrl, setSourceUrl] = useState(defaultValues?.sourceUrl ?? "");

  function handleSelectType(type: PropertyType) {
    setPropertyType(type);
    if (!showUrlInput) {
      onSubmit({ propertyType: type, source: "MANUAL" });
    }
  }

  function handleUrlSubmit() {
    onSubmit({
      propertyType,
      source: "LISTING_URL",
      sourceUrl: sourceUrl.trim() || undefined,
    });
  }

  function handleSkipUrl() {
    setShowUrlInput(false);
    setSourceUrl("");
    onSubmit({ propertyType, source: "MANUAL" });
  }

  return (
    <div className="space-y-6">
      <div>
        <h2
          className="text-2xl font-semibold tracking-tight"
          style={{ color: "var(--brand-navy)", fontFamily: "var(--font-display, Manrope)" }}
        >
          What type of property?
        </h2>
        <p className="text-sm mt-1" style={{ color: "var(--brand-on-surface-variant)" }}>
          Choose the property type to get started.
        </p>
      </div>

      {/* Type cards */}
      <div className="grid grid-cols-2 gap-4">
        <TypeCard
          icon={TreePine}
          label="Land"
          description="Bare plots, farmland, waterfront, or undeveloped parcels"
          active={propertyType === "LAND"}
          onClick={() => handleSelectType("LAND")}
        />
        <TypeCard
          icon={Building2}
          label="Building"
          description="Houses, apartments, shops, offices, or any built structure"
          active={propertyType === "BUILDING"}
          onClick={() => handleSelectType("BUILDING")}
        />
      </div>

      {/* Listing URL toggle */}
      {!showUrlInput ? (
        <button
          type="button"
          onClick={() => setShowUrlInput(true)}
          className="flex items-center gap-1.5 text-xs font-medium transition-opacity hover:opacity-70"
          style={{ color: "var(--brand-on-surface-variant)" }}
        >
          <Link className="w-3.5 h-3.5" />
          Have a listing URL? Paste it to pre-fill details
        </button>
      ) : (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold" style={{ color: "var(--brand-navy)" }}>
              Listing URL
            </span>
            <button
              type="button"
              onClick={handleSkipUrl}
              className="flex items-center gap-1 text-xs transition-opacity hover:opacity-70"
              style={{ color: "var(--brand-on-surface-variant)" }}
            >
              <X className="w-3 h-3" />
              Skip
            </button>
          </div>
          <div className="flex gap-2">
            <Input
              placeholder="https://nigeriapropertycentre.com/…"
              value={sourceUrl}
              onChange={(e) => setSourceUrl(e.target.value)}
              className="flex-1"
            />
            <button
              type="button"
              onClick={handleUrlSubmit}
              className="px-4 py-2 rounded-md text-sm font-bold text-white transition-opacity hover:opacity-90 whitespace-nowrap"
              style={{ backgroundColor: "var(--brand-viridian)" }}
            >
              Continue
            </button>
          </div>
          <p className="text-xs" style={{ color: "var(--brand-on-surface-variant)" }}>
            We&apos;ll try to extract property details from the listing automatically. You can edit them on the next step.
          </p>
        </div>
      )}
    </div>
  );
}

function TypeCard({
  icon: Icon,
  label,
  description,
  active,
  onClick,
}: {
  icon: React.ElementType;
  label: string;
  description: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex flex-col items-start gap-3 p-4 rounded-xl text-left transition-all duration-150"
      style={{
        backgroundColor: active ? "rgba(63,102,83,0.08)" : "var(--brand-surface-low)",
        border: active ? "2px solid var(--brand-viridian)" : "2px solid transparent",
        outline: "none",
      }}
    >
      <div
        className="w-10 h-10 rounded-xl flex items-center justify-center"
        style={{ backgroundColor: active ? "rgba(63,102,83,0.15)" : "rgba(0,13,34,0.06)" }}
      >
        <Icon className="w-5 h-5" style={{ color: active ? "var(--brand-viridian)" : "var(--brand-on-surface-variant)" }} />
      </div>
      <div>
        <div className="text-sm font-bold" style={{ color: "var(--brand-navy)" }}>
          {label}
        </div>
        <div className="text-xs mt-0.5" style={{ color: "var(--brand-on-surface-variant)" }}>
          {description}
        </div>
      </div>
    </button>
  );
}
