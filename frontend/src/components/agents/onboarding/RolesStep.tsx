"use client";

import { FileSearch, Footprints, Ruler, Scale } from "lucide-react";
import { AgentRole } from "@/types/agent";
import { SelectableCard } from "@components/ui/SelectableCard";

// Each selectable role: icon, plain-language title, what the work is, and whether a
// professional licence gate applies (surfaced up-front so applicants self-select honestly).
const ROLE_META: Record<AgentRole, { title: string; desc: string; icon: typeof Footprints; licence?: string }> = {
  [AgentRole.FIELD]: { title: "Field Agent", desc: "Physical site inspection and photo evidence", icon: Footprints },
  [AgentRole.SURVEYOR]: {
    title: "Surveyor",
    desc: "Boundary and location confirmation",
    icon: Ruler,
    licence: "SURCON licence",
  },
  [AgentRole.REGISTRY]: { title: "Registry Agent", desc: "Land-registry title search", icon: FileSearch },
  [AgentRole.LAWYER]: {
    title: "Lawyer",
    desc: "Title verification and legal opinion",
    icon: Scale,
    licence: "NBA licence",
  },
};

interface Props {
  value: AgentRole[];
  onChange: (roles: AgentRole[]) => void;
}

export default function RolesStep({ value, onChange }: Props) {
  const toggle = (role: AgentRole) => {
    onChange(value.includes(role) ? value.filter((r) => r !== role) : [...value, role]);
  };

  return (
    <div className="space-y-4" data-testid="agent-apply-roles">
      <p className="text-sm text-muted-foreground">
        Pick all that apply — you&apos;re reviewed separately for each role. You can add more later.
      </p>
      <div className="grid gap-3 sm:grid-cols-2">
        {(Object.keys(ROLE_META) as AgentRole[]).map((role) => {
          const { title, desc, icon, licence } = ROLE_META[role];
          return (
            <SelectableCard
              key={role}
              selectionMode="checkbox"
              selected={value.includes(role)}
              onSelect={() => toggle(role)}
              icon={icon}
              title={title}
              description={desc}
              testId={`agent-apply-role-${role.toLowerCase()}`}
              footer={
                licence && (
                  <span className="mt-1.5 inline-flex items-center rounded-full bg-amber-500/10 px-2 py-0.5 text-xs font-medium text-amber-700 dark:text-amber-400">
                    {licence} required
                  </span>
                )
              }
            />
          );
        })}
      </div>
    </div>
  );
}
