"use client";

import { useEffect, useRef, useState } from "react";
import { MapPin, AlertCircle } from "lucide-react";
import { Button } from "@3rdparty/ui/button";
import { Input } from "@3rdparty/ui/input";
import { setOptions, importLibrary } from "@googlemaps/js-api-loader";
import { nigerianStates, getLgasForState } from "@lib/nigerianLocations";
import { publicConfig } from "@lib/config/public";

export interface LocationStepValues {
  state: string;
  lga?: string;
  addressLine?: string;
  lat?: number;
  lng?: number;
  landmarkDescription: string;
}

interface Props {
  defaultValues?: Partial<LocationStepValues>;
  pending?: boolean;
  onBack: () => void;
  onSubmit: (values: LocationStepValues) => void;
}

function normaliseState(value: string): string {
  return value.replace(/-/g, "_").toUpperCase();
}

function extractAddressComponent(
  components: google.maps.GeocoderAddressComponent[],
  types: string[],
): string | null {
  for (const comp of components) {
    if (types.some((t) => comp.types.includes(t))) {
      return comp.long_name;
    }
  }
  return null;
}

function stateNameToValue(stateName: string): string | null {
  const lower = stateName.toLowerCase().replace(/\s+state$/i, "").trim();
  const match = nigerianStates.find(
    (s) => s.label.toLowerCase() === lower || s.value === lower.replace(/\s/g, "-"),
  );
  return match?.value ?? null;
}

export default function LocationStep({ defaultValues, pending, onBack, onSubmit }: Props) {
  const [stateValue, setStateValue] = useState(
    defaultValues?.state?.toLowerCase().replace(/_/g, "-") ?? "lagos",
  );
  const [lga, setLga] = useState(defaultValues?.lga ?? "");
  const [addressLine, setAddressLine] = useState(defaultValues?.addressLine ?? "");
  const [lat, setLat] = useState<number | undefined>(defaultValues?.lat);
  const [lng, setLng] = useState<number | undefined>(defaultValues?.lng);
  const [landmark, setLandmark] = useState(defaultValues?.landmarkDescription ?? "");
  const [error, setError] = useState<string | null>(null);

  const addressInputRef = useRef<HTMLInputElement>(null);
  const autocompleteRef = useRef<google.maps.places.Autocomplete | null>(null);
  const [mapsLoaded, setMapsLoaded] = useState(false);

  useEffect(() => {
    const apiKey = publicConfig.googleMapsApiKey;
    if (!apiKey) return;

    setOptions({ key: apiKey });
    importLibrary("places").then(() => setMapsLoaded(true)).catch(() => {});
  }, []);

  useEffect(() => {
    if (!mapsLoaded || !addressInputRef.current) return;

    const ac = new google.maps.places.Autocomplete(addressInputRef.current, {
      componentRestrictions: { country: "ng" },
      fields: ["address_components", "formatted_address", "geometry"],
    });
    autocompleteRef.current = ac;

    const listener = ac.addListener("place_changed", () => {
      const place = ac.getPlace();
      if (!place.address_components) return;

      const formatted = place.formatted_address ?? "";
      setAddressLine(formatted);

      const stateName = extractAddressComponent(place.address_components, [
        "administrative_area_level_1",
      ]);
      if (stateName) {
        const sv = stateNameToValue(stateName);
        if (sv) {
          setStateValue(sv);
          setLga("");
        }
      }

      if (place.geometry?.location) {
        setLat(place.geometry.location.lat());
        setLng(place.geometry.location.lng());
      }
    });

    return () => google.maps.event.removeListener(listener);
  }, [mapsLoaded]);

  function handleSubmit() {
    setError(null);
    if (!stateValue) {
      setError("Select the property state.");
      return;
    }
    if (!landmark || landmark.length < 5) {
      setError("Landmark description is required to help agents find the exact spot.");
      return;
    }
    onSubmit({
      state: normaliseState(stateValue),
      lga: lga || undefined,
      addressLine: addressLine || undefined,
      lat,
      lng,
      landmarkDescription: landmark,
    });
  }

  return (
    <div className="space-y-6">
      <div>
        <h2
          className="text-2xl font-semibold tracking-tight"
          style={{ color: "var(--brand-navy)", fontFamily: "var(--font-display, Manrope)" }}
        >
          Where is this property?
        </h2>
        <p className="text-sm mt-1" style={{ color: "var(--brand-on-surface-variant)" }}>
          Help our agents find the right location.
        </p>
      </div>

      {/* Address input with Google Maps */}
      <div>
        <label
          className="text-xs font-semibold block mb-1.5"
          style={{ color: "var(--brand-on-surface-variant)" }}
        >
          Property address
        </label>
        <input
          ref={addressInputRef}
          type="text"
          placeholder="Start typing to search an address in Nigeria…"
          value={addressLine}
          onChange={(e) => setAddressLine(e.target.value)}
          className="w-full rounded-md py-2.5 px-3 text-sm"
          style={{
            backgroundColor: "var(--brand-surface-card)",
            color: "var(--brand-navy)",
            border: "1px solid var(--border)",
          }}
        />
        {!publicConfig.googleMapsApiKey && (
          <p className="text-xs mt-1" style={{ color: "var(--brand-on-surface-variant)" }}>
            Address autocomplete not configured — enter manually.
          </p>
        )}
      </div>

      {/* State + LGA — always editable even after Maps pre-fill */}
      <div className="grid sm:grid-cols-2 gap-3">
        <label>
          <span
            className="text-xs font-medium block mb-1.5"
            style={{ color: "var(--brand-on-surface-variant)" }}
          >
            State <span style={{ color: "var(--destructive)" }}>*</span>
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

      {/* Landmark — always visible and required */}
      <div>
        <div
          className="text-xs font-semibold mb-1.5 flex items-center gap-1.5"
          style={{ color: "var(--brand-on-surface-variant)" }}
        >
          <MapPin className="w-3.5 h-3.5" />
          Landmark description <span style={{ color: "var(--destructive)" }}>*</span>
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
        <p className="text-xs mt-1" style={{ color: "var(--brand-on-surface-variant)" }}>
          Help agents find the exact spot — nearest junction, local landmark, or any recognisable reference.
        </p>
      </div>

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
          {pending ? "Saving…" : "Continue"}
        </Button>
      </div>
    </div>
  );
}
