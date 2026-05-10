"use client";

import { useState } from "react";
import { Button } from "@3rdparty/ui/button";
import { Check, MapPin, Ruler, FileText, Scale } from "lucide-react";
import type { AgentType } from "../libs/agent-service";

interface TypeOption {
  type: AgentType;
  title: string;
  blurb: string;
  responsibilities: string[];
  icon: typeof MapPin;
}

const OPTIONS: TypeOption[] = [
  {
    type: "FIELD",
    title: "Field Agent",
    blurb: "Visit and document properties on the ground.",
    responsibilities: [
      "On-site property inspection",
      "GPS-stamped photos & video",
      "Neighbourhood condition reports",
    ],
    icon: MapPin,
  },
  {
    type: "SURVEYOR",
    title: "Surveyor",
    blurb: "Confirm boundaries and verify survey plans.",
    responsibilities: [
      "Boundary verification",
      "Survey plan authentication",
      "Coordinate capture",
    ],
    icon: Ruler,
  },
  {
    type: "REGISTRY",
    title: "Registry Agent",
    blurb: "Search registries for title authenticity.",
    responsibilities: [
      "Title document search",
      "Ownership chain verification",
      "Encumbrance discovery",
    ],
    icon: FileText,
  },
  {
    type: "LAWYER",
    title: "Lawyer (NBA)",
    blurb: "Render the structured legal opinion in Premium reports.",
    responsibilities: [
      "Legal opinion drafting",
      "Risk flagging & recommendation",
      "NBA-licensed sign-off",
    ],
    icon: Scale,
  },
];

interface Props {
  defaultValue: AgentType[];
  pending?: boolean;
  onSubmit: (types: AgentType[]) => void;
}

export default function TypeSelectionStep({ defaultValue, pending, onSubmit }: Props) {
  const [selected, setSelected] = useState<Set<AgentType>>(new Set(defaultValue));

  const toggle = (type: AgentType) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  };

  const list = Array.from(selected);
  const canContinue = list.length > 0;

  return (
    <div className="space-y-6">
      <div>
        <h2
          className="text-2xl font-semibold tracking-tight"
          style={{ color: "var(--brand-navy)", fontFamily: "var(--font-display, Manrope)" }}
        >
          What kind of agent are you?
        </h2>
        <p className="text-sm mt-1" style={{ color: "var(--brand-on-surface-variant)" }}>
          Pick all that apply. You will be reviewed for each role you select.
        </p>
      </div>

      <div className="grid sm:grid-cols-2 gap-3">
        {OPTIONS.map((opt) => {
          const isOn = selected.has(opt.type);
          const Icon = opt.icon;
          return (
            <button
              key={opt.type}
              type="button"
              onClick={() => toggle(opt.type)}
              aria-pressed={isOn}
              data-testid={`agent-wizard-type-${opt.type.toLowerCase()}`}
              className="text-left rounded-xl p-4 transition-all"
              style={{
                backgroundColor: isOn ? "var(--brand-viridian-xlight)" : "var(--brand-surface-card)",
                boxShadow: isOn
                  ? "0 0 0 2px var(--brand-viridian), 0px 12px 24px rgba(0,13,34,0.06)"
                  : "0px 12px 24px rgba(0,13,34,0.04)",
              }}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-3">
                  <span
                    className="w-9 h-9 rounded-lg flex items-center justify-center"
                    style={{
                      backgroundColor: isOn ? "var(--brand-viridian)" : "var(--brand-surface-low)",
                      color: isOn ? "white" : "var(--brand-navy)",
                    }}
                  >
                    <Icon className="w-4 h-4" />
                  </span>
                  <div>
                    <div
                      className="font-semibold text-sm"
                      style={{ color: "var(--brand-navy)" }}
                    >
                      {opt.title}
                    </div>
                  </div>
                </div>
                {isOn && (
                  <span
                    className="w-5 h-5 rounded-full flex items-center justify-center"
                    style={{ backgroundColor: "var(--brand-viridian)" }}
                  >
                    <Check className="w-3 h-3 text-white" strokeWidth={3} />
                  </span>
                )}
              </div>
              <p
                className="text-xs mt-2"
                style={{ color: "var(--brand-on-surface-variant)" }}
              >
                {opt.blurb}
              </p>
              <ul className="mt-3 space-y-1">
                {opt.responsibilities.map((r) => (
                  <li
                    key={r}
                    className="text-xs flex items-start gap-2"
                    style={{ color: "var(--brand-on-surface)" }}
                  >
                    <span
                      className="w-1 h-1 rounded-full mt-1.5 shrink-0"
                      style={{ backgroundColor: "var(--brand-viridian)" }}
                    />
                    {r}
                  </li>
                ))}
              </ul>
            </button>
          );
        })}
      </div>

      <div className="flex justify-end pt-2">
        <Button
          type="button"
          data-testid="agent-wizard-types-continue"
          disabled={!canContinue || pending}
          onClick={() => onSubmit(list)}
        >
          {pending ? "Saving…" : "Continue"}
        </Button>
      </div>
    </div>
  );
}
