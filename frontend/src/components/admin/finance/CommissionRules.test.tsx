import { describe, it, expect, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { AgentRole } from "@/types/agent";
import { CommissionRule } from "@/types/commission";

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

const rulesResult: { data: CommissionRule[] | null; isLoading: boolean; isError: boolean } = {
  data: null,
  isLoading: false,
  isError: false,
};

vi.mock("./libs/useFinanceQueries", () => ({
  useCommissionRulesQuery: () => rulesResult,
  useSetCommissionRuleMutation: () => ({ mutate: vi.fn(), isPending: false }),
}));

import CommissionRules from "./CommissionRules";

const rule = (role: AgentRole, amountNgnKobo: number): CommissionRule => ({
  id: `rule-${role}`,
  role,
  amountNgnKobo,
  dateCreated: "2026-09-27T00:00:00Z",
});

/** §20.1 / D97: one fixed ₦ amount per role, the same on every tier. */
describe("CommissionRules", () => {
  it("lists one editable naira amount per role, with no tier", () => {
    rulesResult.data = [rule(AgentRole.REGISTRY, 2_000_000), rule(AgentRole.LAWYER, 3_600_000)];
    const html = renderToStaticMarkup(<CommissionRules />);
    expect(html).toContain("rule-REGISTRY");
    expect(html).toContain("rule-input-LAWYER");
    // Stored in kobo, edited in naira.
    expect(html).toContain('value="20000"');
    expect(html).toContain('value="36000"');
    // Roles are humanized, and the grid no longer has a tier axis.
    expect(html).toContain("Registry");
    expect(html).not.toContain(">REGISTRY<");
    expect(html).not.toContain("Tier");
  });
});
