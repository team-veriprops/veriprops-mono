"use client";

import { useMemo, useState } from "react";
import { Button } from "@3rdparty/ui/button";
import { Input } from "@3rdparty/ui/input";
import { AlertCircle, X } from "lucide-react";
import { nigerianStates, getLgasForState } from "@lib/nigerianLocations";
import type {
  AgentApplication,
  AgentType,
  CredentialsStepRequest,
} from "../libs/agent-service";
import { validateCredentialsStep } from "./wizardUtils";

interface Props {
  application: AgentApplication;
  pending?: boolean;
  onBack: () => void;
  onSubmit: (req: CredentialsStepRequest) => void;
}

const stateLabel = new Map(nigerianStates.map((s) => [s.value, s.label]));

function normaliseState(value: string): string {
  // Backend expects ABIA, AKWA_IBOM, FCT etc.
  return value.replace(/-/g, "_").toUpperCase();
}

export default function CredentialsStep({ application, pending, onBack, onSubmit }: Props) {
  const types = application.types;
  const needsSurveyor = types.includes("SURVEYOR" as AgentType);
  const needsLawyer = types.includes("LAWYER" as AgentType);

  const [surveyorLicenceNo, setSurveyorLicenceNo] = useState(application.surveyorLicenceNo ?? "");
  const [surveyorLicenceUrl, setSurveyorLicenceUrl] = useState("");
  const [nbaLicenceNo, setNbaLicenceNo] = useState(application.nbaLicenceNo ?? "");
  const [nbaLicenceUrl, setNbaLicenceUrl] = useState("");
  const [yearsOfExperience, setYearsOfExperience] = useState<string>(
    application.yearsOfExperience ? String(application.yearsOfExperience) : "",
  );
  const [bio, setBio] = useState(application.bio ?? "");

  const [coverageStates, setCoverageStates] = useState<string[]>(() => {
    const lower = application.coverageStates.map((s) => s.toLowerCase().replace(/_/g, "-"));
    return lower.filter((s) => stateLabel.has(s));
  });
  const [coverageLgas, setCoverageLgas] = useState<string[]>(application.coverageLgas);
  const [error, setError] = useState<string | null>(null);

  const lgaOptions = useMemo(() => {
    const options: { value: string; label: string; state: string }[] = [];
    for (const s of coverageStates) {
      for (const lga of getLgasForState(s)) {
        options.push({ value: lga.value, label: `${lga.label}, ${stateLabel.get(s)}`, state: s });
      }
    }
    return options;
  }, [coverageStates]);

  const toggleState = (value: string) => {
    setCoverageStates((prev) => {
      const next = prev.includes(value) ? prev.filter((v) => v !== value) : [...prev, value];
      // Drop LGAs whose parent state is no longer selected.
      const allowed = new Set(next);
      setCoverageLgas((lgas) => lgas.filter((l) => allowed.has(l.split(":")[0] ?? "")));
      return next;
    });
  };

  const toggleLga = (value: string, state: string) => {
    const id = `${state}:${value}`;
    setCoverageLgas((prev) => (prev.includes(id) ? prev.filter((v) => v !== id) : [...prev, id]));
  };

  const handleSubmit = () => {
    setError(null);
    const validation = validateCredentialsStep(types, {
      surveyorLicenceNo,
      surveyorLicenceUrl,
      nbaLicenceNo,
      nbaLicenceUrl,
      coverageStates,
      bio,
    });
    if (!validation.valid) {
      setError(validation.error);
      return;
    }
    onSubmit({
      surveyorLicenceNo: surveyorLicenceNo || undefined,
      surveyorLicenceUrl: surveyorLicenceUrl || undefined,
      nbaLicenceNo: nbaLicenceNo || undefined,
      nbaLicenceUrl: nbaLicenceUrl || undefined,
      yearsOfExperience: yearsOfExperience ? Number(yearsOfExperience) : undefined,
      coverageStates: coverageStates.map(normaliseState),
      coverageLgas,
      bio: bio || undefined,
    });
  };

  return (
    <div className="space-y-6">
      <div>
        <h2
          className="text-2xl font-semibold tracking-tight"
          style={{ color: "var(--brand-navy)", fontFamily: "var(--font-display, Manrope)" }}
        >
          Credentials & coverage
        </h2>
        <p className="text-sm mt-1" style={{ color: "var(--brand-on-surface-variant)" }}>
          Tell us where you can work and any licences we should review.
        </p>
      </div>

      {needsSurveyor && (
        <Section title="Surveyor licence">
          <div className="grid sm:grid-cols-2 gap-3">
            <Input
              placeholder="Licence number"
              data-testid="agent-wizard-surveyor-licence"
              value={surveyorLicenceNo}
              onChange={(e) => setSurveyorLicenceNo(e.target.value)}
            />
            <Input
              placeholder="Licence document URL"
              value={surveyorLicenceUrl}
              onChange={(e) => setSurveyorLicenceUrl(e.target.value)}
            />
          </div>
        </Section>
      )}

      {needsLawyer && (
        <Section title="NBA / Bar licence">
          <div className="grid sm:grid-cols-2 gap-3">
            <Input
              placeholder="NBA call number"
              data-testid="agent-wizard-nba-licence"
              value={nbaLicenceNo}
              onChange={(e) => setNbaLicenceNo(e.target.value)}
            />
            <Input
              placeholder="NBA licence document URL"
              value={nbaLicenceUrl}
              onChange={(e) => setNbaLicenceUrl(e.target.value)}
            />
          </div>
        </Section>
      )}

      <Section title="Experience & bio">
        <div className="grid sm:grid-cols-2 gap-3 items-start">
          <Input
            inputMode="numeric"
            placeholder="Years of experience"
            data-testid="agent-wizard-experience"
            value={yearsOfExperience}
            onChange={(e) => setYearsOfExperience(e.target.value.replace(/\D/g, ""))}
          />
        </div>
        <textarea
          rows={4}
          maxLength={300}
          data-testid="agent-wizard-bio"
          placeholder="Tell us a bit about you (max 300 chars)…"
          className="w-full rounded-md p-3 text-sm"
          style={{
            backgroundColor: "var(--brand-surface-card)",
            border: "1px solid var(--border)",
            color: "var(--brand-navy)",
          }}
          value={bio}
          onChange={(e) => setBio(e.target.value)}
        />
        <div
          className="text-[11px] text-right"
          style={{ color: "var(--brand-on-surface-variant)" }}
        >
          {bio.length} / 300
        </div>
      </Section>

      <Section title="Coverage states">
        <div className="flex flex-wrap gap-2">
          {nigerianStates.map((s) => {
            const isOn = coverageStates.includes(s.value);
            return (
              <button
                key={s.value}
                type="button"
                onClick={() => toggleState(s.value)}
                className="text-xs rounded-full px-3 py-1.5 transition-colors"
                style={{
                  backgroundColor: isOn ? "var(--brand-viridian)" : "var(--brand-surface-low)",
                  color: isOn ? "white" : "var(--brand-on-surface)",
                }}
              >
                {s.label}
              </button>
            );
          })}
        </div>
      </Section>

      {coverageStates.length > 0 && (
        <Section title="Coverage LGAs (optional)">
          <div
            className="rounded-md p-3 max-h-48 overflow-y-auto"
            style={{
              backgroundColor: "var(--brand-surface-low)",
            }}
          >
            <div className="flex flex-wrap gap-2">
              {lgaOptions.map((opt) => {
                const id = `${opt.state}:${opt.value}`;
                const isOn = coverageLgas.includes(id);
                return (
                  <button
                    key={id}
                    type="button"
                    onClick={() => toggleLga(opt.value, opt.state)}
                    className="text-xs rounded-full px-2.5 py-1 transition-colors"
                    style={{
                      backgroundColor: isOn ? "var(--brand-navy)" : "white",
                      color: isOn ? "white" : "var(--brand-on-surface)",
                    }}
                  >
                    {opt.label}
                    {isOn && <X className="w-3 h-3 ml-1 inline-block" />}
                  </button>
                );
              })}
            </div>
          </div>
        </Section>
      )}

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

      <div className="flex justify-between pt-2">
        <Button type="button" variant="outline" data-testid="agent-wizard-credentials-back" onClick={onBack}>
          Back
        </Button>
        <Button type="button" data-testid="agent-wizard-credentials-continue" disabled={pending} onClick={handleSubmit}>
          {pending ? "Saving…" : "Continue"}
        </Button>
      </div>
    </div>
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
