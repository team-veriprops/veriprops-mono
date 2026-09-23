"use client";

import { useEffect, useId } from "react";
import { BadgeCheck } from "lucide-react";
import {
  AgentCredentialInput,
  AgentRole,
  ROLE_REQUIRED_CREDENTIAL,
} from "@/types/agent";
import { Input } from "@3rdparty/ui/input";
import { Label } from "@3rdparty/ui/label";
import { Textarea } from "@3rdparty/ui/textarea";
import { humanizeEnumLabel } from "@lib/utils";
import { AgentWizardState } from "./types";

interface Props {
  state: AgentWizardState;
  update: (patch: Partial<AgentWizardState>) => void;
}

export default function CredentialsStep({ state, update }: Props) {
  // One prefix for this step's controls; each field appends its own key so every label points
  // at exactly the input beneath it.
  const fieldIdPrefix = useId();

  // Roles that need a professional licence drive the credential rows.
  const requiredRoles = state.roles.filter((r) => ROLE_REQUIRED_CREDENTIAL[r]);

  // Keep a credential row for every role that requires one; drop stale rows.
  useEffect(() => {
    const next: AgentCredentialInput[] = requiredRoles.map((role) => {
      const existing = state.credentials.find((c) => c.role === role);
      return existing ?? { role, credentialType: ROLE_REQUIRED_CREDENTIAL[role]! };
    });
    const changed =
      next.length !== state.credentials.length ||
      next.some((c, i) => c.role !== state.credentials[i]?.role);
    if (changed) update({ credentials: next });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.roles]);

  const setCredential = (role: AgentRole, patch: Partial<AgentCredentialInput>) => {
    update({
      credentials: state.credentials.map((c) => (c.role === role ? { ...c, ...patch } : c)),
    });
  };

  return (
    <div className="space-y-6" data-testid="agent-apply-credentials">
      {requiredRoles.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          None of your selected roles require a professional licence. Add optional details below.
        </p>
      ) : (
        <div className="space-y-4">
          <h2 className="font-medium text-foreground">Professional credentials</h2>
          {requiredRoles.map((role) => {
            const cred = state.credentials.find((c) => c.role === role);
            return (
              <div key={role} className="rounded-xl border border-border bg-card p-4 shadow-card">
                <p className="mb-3 flex items-center gap-2 text-sm font-semibold text-foreground">
                  <BadgeCheck className="size-4 shrink-0 text-primary" />
                  {humanizeEnumLabel(role)}
                  <span className="font-normal text-muted-foreground">
                    · {humanizeEnumLabel(ROLE_REQUIRED_CREDENTIAL[role]!)}
                  </span>
                </p>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor={`${fieldIdPrefix}-licence-${role}`}>Licence number</Label>
                    <Input
                      id={`${fieldIdPrefix}-licence-${role}`}
                      value={cred?.licenceNumber ?? ""}
                      onChange={(e) => setCredential(role, { licenceNumber: e.target.value })}
                      data-testid={`agent-apply-licence-${role.toLowerCase()}`}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor={`${fieldIdPrefix}-expiry-${role}`}>Expiry date</Label>
                    <Input
                      id={`${fieldIdPrefix}-expiry-${role}`}
                      type="date"
                      value={cred?.expiryDate ?? ""}
                      onChange={(e) => setCredential(role, { expiryDate: e.target.value })}
                      data-testid={`agent-apply-expiry-${role.toLowerCase()}`}
                    />
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor={`${fieldIdPrefix}-experience`}>Years of experience (optional)</Label>
          <Input
            id={`${fieldIdPrefix}-experience`}
            data-testid="agent-apply-experience"
            type="number"
            min={0}
            value={state.yearsExperience ?? ""}
            onChange={(e) =>
              update({ yearsExperience: e.target.value ? Number(e.target.value) : undefined })
            }
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor={`${fieldIdPrefix}-coverage`}>Primary coverage state (optional)</Label>
          <Input
            id={`${fieldIdPrefix}-coverage`}
            data-testid="agent-apply-coverage"
            value={state.coverage[0]?.state ?? ""}
            onChange={(e) =>
              update({ coverage: e.target.value ? [{ state: e.target.value }] : [] })
            }
            placeholder="e.g. Lagos"
          />
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor={`${fieldIdPrefix}-bio`}>Short bio (optional, 300 chars)</Label>
        <Textarea
          id={`${fieldIdPrefix}-bio`}
          data-testid="agent-apply-bio"
          maxLength={300}
          value={state.bio ?? ""}
          onChange={(e) => update({ bio: e.target.value })}
          placeholder="Tell us about your experience"
        />
      </div>
    </div>
  );
}
