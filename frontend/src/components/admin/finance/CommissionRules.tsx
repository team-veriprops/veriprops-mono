"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@3rdparty/ui/button";
import { Input } from "@3rdparty/ui/input";
import { AsyncStateComponent } from "@components/ui/AsyncStateComponent";
import { PageShell } from "@components/ui/PageShell";
import { humanizeEnumLabel } from "@lib/utils";
import { getErrorMessage } from "@lib/errors";
import { CommissionRule } from "@/types/commission";
import { useCommissionRulesQuery, useSetCommissionRuleMutation } from "./libs/useFinanceQueries";

/** Kobo per naira — amounts are stored in kobo and edited in naira. */
const KOBO_PER_NAIRA = 100;

/**
 * Commission Rules admin (§20.1 / D97): the fixed amount one approved task pays an agent, per
 * role. It does not vary by tier, so no job pays more for the same work — the agent sees this
 * figure on the task before accepting it.
 */
export default function CommissionRules() {
  const { data, isLoading, isError } = useCommissionRulesQuery();

  return (
    <PageShell
      title="Commission rules"
      description="Fixed amount paid per approved task, the same on every tier. Shown to the agent before they accept a job."
      width="narrow"
    >
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
                  <th className="p-3">Role</th>
                  <th className="p-3">Amount (₦)</th>
                  <th className="p-3" />
                </tr>
              </thead>
              <tbody className="divide-y">
                {/* Key on the amount so a saved change remounts the row with fresh input state. */}
                {rules.map((r) => <RuleRow key={`${r.id}-${r.amountNgnKobo}`} rule={r} />)}
              </tbody>
            </table>
          </div>
        )}
      </AsyncStateComponent>
    </PageShell>
  );
}

function RuleRow({ rule }: { rule: CommissionRule }) {
  const [naira, setNaira] = useState((rule.amountNgnKobo / KOBO_PER_NAIRA).toString());
  const save = useSetCommissionRuleMutation();

  const kobo = Math.round(Number(naira) * KOBO_PER_NAIRA);
  const dirty = kobo !== rule.amountNgnKobo;

  const submit = () => {
    if (naira.trim() === "" || Number.isNaN(kobo) || kobo < 0) {
      toast.error("Enter an amount of ₦0 or more.");
      return;
    }
    save.mutate(
      { role: rule.role, req: { amountNgnKobo: kobo } },
      {
        onSuccess: () => toast.success("Commission updated."),
        onError: (err) => toast.error(getErrorMessage(err, "Could not update the commission.")),
      },
    );
  };

  return (
    <tr data-testid={`rule-${rule.role}`}>
      <td className="p-3 font-medium">{humanizeEnumLabel(rule.role)}</td>
      <td className="p-3">
        <Input value={naira} inputMode="decimal" onChange={(e) => setNaira(e.target.value)}
          aria-label={`${humanizeEnumLabel(rule.role)} commission in naira`}
          className="h-8 w-32" data-testid={`rule-input-${rule.role}`} />
      </td>
      <td className="p-3 text-right">
        <Button size="sm" variant="outline" disabled={!dirty || save.isPending} onClick={submit}>Save</Button>
      </td>
    </tr>
  );
}
