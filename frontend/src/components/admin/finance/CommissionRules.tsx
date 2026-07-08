"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@3rdparty/ui/button";
import { Input } from "@3rdparty/ui/input";
import { AsyncStateComponent } from "@components/ui/AsyncStateComponent";
import { humanizeEnumLabel } from "@lib/utils";
import { CommissionRule } from "@/types/commission";
import { AgentRole } from "@/types/agent";
import { VerificationTier } from "@/types/verification";
import { useCommissionRulesQuery, useSetCommissionRuleMutation } from "./libs/useFinanceQueries";

/**
 * Commission Rules admin (§15.1 / D30): the agent commission rate per role × tier, editable
 * as a percentage of the tier price. Rates are stored in basis points; shown here as percent.
 */
export default function CommissionRules() {
  const { data, isLoading, isError } = useCommissionRulesQuery();

  return (
    <div className="mx-auto max-w-3xl p-4 sm:p-6">
      <header className="mb-4">
        <h1 className="text-lg font-semibold">Commission rules</h1>
        <p className="text-sm text-muted-foreground">
          Agent share of the tier price, per role. Shown to the agent before they accept a job.
        </p>
      </header>
      <AsyncStateComponent<CommissionRule[]>
        isLoading={isLoading}
        isError={isError}
        data={data}
        loadingText="Loading rules…"
        emptyText="No commission rules configured."
      >
        {(rules) => (
          <div className="overflow-x-auto rounded-lg border">
            <table className="w-full text-sm">
              <thead className="bg-muted/50 text-left text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="p-3">Tier</th>
                  <th className="p-3">Role</th>
                  <th className="p-3">Rate (%)</th>
                  <th className="p-3" />
                </tr>
              </thead>
              <tbody className="divide-y">
                {/* Key on the rate so a saved change remounts the row with fresh input state. */}
                {rules.map((r) => <RuleRow key={`${r.id}-${r.rateBps}`} rule={r} />)}
              </tbody>
            </table>
          </div>
        )}
      </AsyncStateComponent>
    </div>
  );
}

function RuleRow({ rule }: { rule: CommissionRule }) {
  const [pct, setPct] = useState((rule.rateBps / 100).toString());
  const save = useSetCommissionRuleMutation();

  const dirty = Math.round(Number(pct) * 100) !== rule.rateBps;

  const submit = () => {
    const bps = Math.round(Number(pct) * 100);
    if (Number.isNaN(bps) || bps < 0 || bps > 10_000) {
      toast.error("Enter a rate between 0 and 100%.");
      return;
    }
    save.mutate(
      { tier: rule.tier as VerificationTier, role: rule.role as AgentRole, req: { rateBps: bps } },
      { onSuccess: () => toast.success("Rate updated."), onError: () => toast.error("Could not update the rate.") },
    );
  };

  return (
    <tr data-testid={`rule-${rule.tier}-${rule.role}`}>
      <td className="p-3 font-medium">{humanizeEnumLabel(rule.tier)}</td>
      <td className="p-3">{humanizeEnumLabel(rule.role)}</td>
      <td className="p-3">
        <Input value={pct} inputMode="decimal" onChange={(e) => setPct(e.target.value)}
          className="h-8 w-24" data-testid={`rule-input-${rule.tier}-${rule.role}`} />
      </td>
      <td className="p-3 text-right">
        <Button size="sm" variant="outline" disabled={!dirty || save.isPending} onClick={submit}>Save</Button>
      </td>
    </tr>
  );
}
