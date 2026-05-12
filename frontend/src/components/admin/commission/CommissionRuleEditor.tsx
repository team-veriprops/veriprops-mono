"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Plus, Pencil } from "lucide-react";
import { commissionAdminService, CommissionRule } from "@components/agents/earnings/libs/earnings-service";
import { useState } from "react";
import { getErrorMessage } from "@lib/utils";

const ROLES = ["SURVEYOR", "LAWYER", "INSPECTOR", "REGISTRY"];
const TIERS = ["BASIC", "STANDARD", "PREMIUM", "ENTERPRISE"];

interface FormState {
  role: string;
  tier: string;
  percentage: string;
  effectiveDate: string;
}

const defaultForm: FormState = {
  role: ROLES[0],
  tier: TIERS[0],
  percentage: "",
  effectiveDate: new Date().toISOString().split("T")[0],
};

const qKey = ["admin", "commission-rules"];

export default function CommissionRuleEditor() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: qKey,
    queryFn: () => commissionAdminService.listRules(),
  });
  const rules: CommissionRule[] = (data as any)?.data ?? [];

  const [form, setForm] = useState<FormState>(defaultForm);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: () => {
      const payload = {
        role: form.role,
        tier: form.tier,
        percentage: parseFloat(form.percentage),
        effectiveDate: form.effectiveDate,
      };
      return editingId
        ? commissionAdminService.updateRule(editingId, payload)
        : commissionAdminService.createRule(payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qKey });
      setForm(defaultForm);
      setEditingId(null);
      setError(null);
    },
    onError: (e: any) => setError(getErrorMessage(e)),
  });

  const startEdit = (rule: CommissionRule) => {
    setEditingId(rule.id);
    setForm({
      role: rule.role,
      tier: rule.tier,
      percentage: String(rule.percentage),
      effectiveDate: rule.effectiveDate,
    });
  };

  const cancelEdit = () => {
    setEditingId(null);
    setForm(defaultForm);
    setError(null);
  };

  if (isLoading) {
    return (
      <div className="flex justify-center py-10">
        <Loader2 className="h-5 w-5 animate-spin text-indigo-500" />
      </div>
    );
  }

  return (
    <div data-testid="commission-rule-editor" className="space-y-6">
      <div className="rounded-lg border border-gray-200 bg-white p-5">
        <h2 className="text-sm font-semibold text-gray-900 mb-4">
          {editingId ? "Edit Rule" : "Add New Rule"}
        </h2>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Role</label>
            <select
              value={form.role}
              onChange={(e) => setForm((f) => ({ ...f, role: e.target.value }))}
              style={{ cursor: "pointer" }}
              className="w-full rounded border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              data-testid="commission-rule-role"
            >
              {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Tier</label>
            <select
              value={form.tier}
              onChange={(e) => setForm((f) => ({ ...f, tier: e.target.value }))}
              style={{ cursor: "pointer" }}
              className="w-full rounded border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              data-testid="commission-rule-tier"
            >
              {TIERS.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Percentage (%)</label>
            <input
              type="number"
              min="0"
              max="100"
              step="0.01"
              value={form.percentage}
              onChange={(e) => setForm((f) => ({ ...f, percentage: e.target.value }))}
              placeholder="e.g. 15.00"
              className="w-full rounded border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              data-testid="commission-rule-percentage"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Effective Date</label>
            <input
              type="date"
              value={form.effectiveDate}
              onChange={(e) => setForm((f) => ({ ...f, effectiveDate: e.target.value }))}
              className="w-full rounded border border-gray-300 px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
              data-testid="commission-rule-effective-date"
            />
          </div>
        </div>
        {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
        <div className="flex gap-2 mt-4">
          <button
            type="button"
            onClick={() => save.mutate()}
            disabled={save.isPending || !form.percentage}
            style={{ cursor: "pointer" }}
            className="inline-flex items-center gap-1.5 rounded-md bg-indigo-600 px-4 py-2 text-xs font-semibold text-white hover:bg-indigo-700 disabled:opacity-60"
            data-testid="commission-rule-save-button"
          >
            <Plus className="h-3.5 w-3.5" />
            {save.isPending ? "Saving…" : editingId ? "Update Rule" : "Add Rule"}
          </button>
          {editingId && (
            <button
              type="button"
              onClick={cancelEdit}
              style={{ cursor: "pointer" }}
              className="rounded-md border border-gray-300 px-4 py-2 text-xs font-medium text-gray-700 hover:bg-gray-50"
            >
              Cancel
            </button>
          )}
        </div>
      </div>

      <div className="overflow-x-auto rounded-lg border border-gray-200">
        <table className="min-w-full text-sm bg-white">
          <thead className="border-b border-gray-200">
            <tr>
              {["Role", "Tier", "Percentage", "Effective Date", ""].map((h) => (
                <th
                  key={h}
                  className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-gray-500"
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {rules.length === 0 ? (
              <tr>
                <td colSpan={5} className="py-6 text-center text-gray-400 text-xs">
                  No commission rules defined.
                </td>
              </tr>
            ) : (
              rules.map((rule) => (
                <tr key={rule.id} data-testid="commission-rule-row">
                  <td className="px-4 py-3 font-medium text-gray-900">{rule.role}</td>
                  <td className="px-4 py-3 text-gray-700">{rule.tier}</td>
                  <td className="px-4 py-3 font-semibold text-indigo-700">{rule.percentage}%</td>
                  <td className="px-4 py-3 text-gray-600">{rule.effectiveDate}</td>
                  <td className="px-4 py-3">
                    <button
                      type="button"
                      onClick={() => startEdit(rule)}
                      style={{ cursor: "pointer" }}
                      className="text-gray-400 hover:text-indigo-600"
                      data-testid="commission-rule-edit-button"
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
