"use client";

import { AgentRole } from "@/types/agent";
import { Checkbox } from "@3rdparty/ui/checkbox";

const ROLE_LABELS: Record<AgentRole, { title: string; desc: string }> = {
  [AgentRole.FIELD]: { title: "Field Agent", desc: "Physical site inspection" },
  [AgentRole.SURVEYOR]: { title: "Surveyor", desc: "Boundary & location confirmation (licence required)" },
  [AgentRole.REGISTRY]: { title: "Registry Agent", desc: "Registry search" },
  [AgentRole.LAWYER]: { title: "Lawyer", desc: "Title verification & legal opinion (NBA licence required)" },
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
        Pick all that apply. You will be reviewed for each role you select.
      </p>
      <div className="grid gap-3 sm:grid-cols-2">
        {(Object.keys(ROLE_LABELS) as AgentRole[]).map((role) => {
          const checked = value.includes(role);
          return (
            <label
              key={role}
              className={`flex cursor-pointer items-start gap-3 rounded-lg border p-4 transition-colors ${
                checked ? "border-primary bg-primary/5" : "border-border hover:bg-accent"
              }`}
            >
              <Checkbox
                checked={checked}
                onCheckedChange={() => toggle(role)}
                data-testid={`agent-apply-role-${role.toLowerCase()}`}
              />
              <span>
                <span className="block font-medium text-foreground">{ROLE_LABELS[role].title}</span>
                <span className="block text-xs text-muted-foreground">{ROLE_LABELS[role].desc}</span>
              </span>
            </label>
          );
        })}
      </div>
    </div>
  );
}
