"use client";

import { useState } from "react";
import { toast } from "sonner";
import { X } from "lucide-react";
import { Button } from "@3rdparty/ui/button";
import { Input } from "@3rdparty/ui/input";
import { Label } from "@3rdparty/ui/label";
import { Card } from "@3rdparty/ui/card";
import { CoverageArea, NigerianState } from "@/types/agentReputation";
import { NigeriaCoverageMap } from "./NigeriaCoverageMap";
import {
  useCoverageQuery,
  useNigeriaLocationsQuery,
  useSetCoverageMutation,
} from "./libs/useReputationQueries";

/**
 * Agent coverage settings (§16.1): declare the states you cover on an interactive map, with an
 * optional travel radius. Changes take effect on new matching immediately. Unusually wide
 * coverage is flagged for admin review server-side (never blocked).
 */
export default function CoverageSettings() {
  const locations = useNigeriaLocationsQuery();
  const coverage = useCoverageQuery();

  const ready = !!locations.data && !!coverage.data;
  return (
    <div className="mx-auto max-w-4xl space-y-4 p-4 sm:p-6">
      <header>
        <h1 className="text-lg font-semibold">Coverage area</h1>
        <p className="text-sm text-muted-foreground">
          Tap the states you can work in. Field and survey jobs are matched to your coverage;
          registry and legal work can be done remotely.
        </p>
      </header>
      {!ready ? (
        <p className="p-6 text-sm text-muted-foreground">Loading map…</p>
      ) : (
        // Keyed so a fresh save re-seeds the form from the saved coverage.
        <CoverageForm
          key={coverage.dataUpdatedAt}
          states={locations.data as NigerianState[]}
          initial={coverage.data as CoverageArea[]}
        />
      )}
    </div>
  );
}

function CoverageForm({ states, initial }: { states: NigerianState[]; initial: CoverageArea[] }) {
  const save = useSetCoverageMutation();
  const [selected, setSelected] = useState<Set<string>>(() => new Set(initial.map((c) => c.state)));
  const [radius, setRadius] = useState(() => {
    const r = initial.find((c) => c.travelRadiusKm != null)?.travelRadiusKm;
    return r != null ? String(r) : "";
  });

  const toggle = (code: string) =>
    setSelected((cur) => {
      const next = new Set(cur);
      if (next.has(code)) next.delete(code);
      else next.add(code);
      return next;
    });

  const submit = () => {
    if (selected.size === 0) {
      toast.error("Select at least one state you cover.");
      return;
    }
    const km = radius ? Number(radius) : null;
    const areas = [...selected].map((state) => ({ state, travelRadiusKm: km }));
    save.mutate(areas, {
      onSuccess: () => toast.success("Coverage updated."),
      onError: (e: unknown) => toast.error((e as Error)?.message ?? "Could not update coverage."),
    });
  };

  return (
    <Card className="space-y-4 p-4">
      <NigeriaCoverageMap states={states} selected={selected} onToggle={toggle} />

      <div className="flex flex-wrap gap-2" data-testid="coverage-chips">
        {[...selected].map((code) => {
          const label = states.find((s) => s.code === code)?.label ?? code;
          return (
            <span key={code} className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-1 text-xs text-emerald-700 dark:text-emerald-300">
              {label}
              <button aria-label={`Remove ${label}`} onClick={() => toggle(code)}>
                <X className="size-3" />
              </button>
            </span>
          );
        })}
        {selected.size === 0 && <span className="text-xs text-muted-foreground">No states selected.</span>}
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <div className="space-y-1">
          <Label htmlFor="coverage-radius">Max travel distance (km, optional)</Label>
          <Input id="coverage-radius" inputMode="numeric" value={radius} className="w-40"
            onChange={(e) => setRadius(e.target.value)} data-testid="coverage-radius" />
        </div>
        <Button onClick={submit} disabled={save.isPending} data-testid="coverage-save">
          Save coverage
        </Button>
      </div>
    </Card>
  );
}
