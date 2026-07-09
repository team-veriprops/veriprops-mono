"use client";

import { useMemo } from "react";
import { NigerianState } from "@/types/agentReputation";
import { cn } from "@lib/utils";

/**
 * Interactive coverage map preview (§16.1). A schematic geo-grid of Nigeria's 37 states —
 * each state is a clickable SVG cell that toggles coverage and highlights when selected. The
 * layout is an approximate north→south, west→east arrangement (not cartographically precise);
 * an exact GeoJSON path set can drop in behind this same component API later. State codes come
 * from the backend canon (D33).
 */

// [row, col] on a north(top)→south grid, west(left)→east.
const LAYOUT: Record<string, [number, number]> = {
  sokoto: [0, 1], zamfara: [0, 2], katsina: [0, 3], kano: [0, 4], jigawa: [0, 5], yobe: [0, 6], borno: [0, 7],
  kebbi: [1, 0], niger: [1, 2], kaduna: [1, 3], bauchi: [1, 5], gombe: [1, 6],
  kwara: [2, 1], fct: [2, 3], plateau: [2, 4], taraba: [2, 6], adamawa: [2, 7],
  oyo: [3, 1], osun: [3, 2], kogi: [3, 3], nasarawa: [3, 4], benue: [3, 5],
  ondo: [4, 1], ekiti: [4, 2], enugu: [4, 4], ebonyi: [4, 5],
  ogun: [5, 0], lagos: [5, 1], edo: [5, 2], anambra: [5, 3], imo: [5, 4], abia: [5, 5], "cross-river": [5, 6],
  delta: [6, 2], bayelsa: [6, 3], rivers: [6, 4], "akwa-ibom": [6, 5],
};

const CELL = 62;
const GAP = 6;
const COLS = 8;
const ROWS = 7;

interface Props {
  states: NigerianState[];
  selected: Set<string>;
  onToggle: (code: string) => void;
}

export function NigeriaCoverageMap({ states, selected, onToggle }: Props) {
  const labelByCode = useMemo(() => new Map(states.map((s) => [s.code, s.label])), [states]);
  const width = COLS * (CELL + GAP);
  const height = ROWS * (CELL + GAP);

  return (
    <div className="overflow-x-auto">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="min-w-[520px] max-w-full"
        role="group"
        aria-label="Nigeria coverage map"
      >
        {states.map((s) => {
          const pos = LAYOUT[s.code];
          if (!pos) return null;
          const [row, col] = pos;
          const x = col * (CELL + GAP);
          const y = row * (CELL + GAP);
          const isOn = selected.has(s.code);
          return (
            <g
              key={s.code}
              transform={`translate(${x}, ${y})`}
              className="cursor-pointer"
              role="checkbox"
              aria-checked={isOn}
              aria-label={s.label}
              tabIndex={0}
              onClick={() => onToggle(s.code)}
              onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && onToggle(s.code)}
            >
              <rect
                width={CELL}
                height={CELL}
                rx={8}
                className={cn(
                  "transition-colors",
                  isOn
                    ? "fill-emerald-500 stroke-emerald-600"
                    : "fill-muted stroke-border hover:fill-muted-foreground/20",
                )}
                strokeWidth={1.5}
              />
              <text
                x={CELL / 2}
                y={CELL / 2}
                textAnchor="middle"
                dominantBaseline="central"
                className={cn("text-[9px] font-medium", isOn ? "fill-white" : "fill-foreground")}
              >
                {(labelByCode.get(s.code) ?? s.code).slice(0, 8)}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
