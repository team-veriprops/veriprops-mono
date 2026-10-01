import { describe, expect, it } from "vitest";
import { AgentRole } from "@/types/agent";
import { CommissionKind } from "@/types/adminVerification";
import { commissionLineLabel } from "./commission";

/** §20.1 / D97: a remote bonus is its own ledger line, named apart from the fixed commission. */
describe("commissionLineLabel", () => {
  it("names a fixed commission by its role", () => {
    expect(commissionLineLabel({ role: AgentRole.FIELD, kind: CommissionKind.BASE })).toBe("Field");
  });

  it("names a remote bonus line as such", () => {
    expect(commissionLineLabel({ role: AgentRole.FIELD, kind: CommissionKind.REMOTE_BONUS })).toBe(
      "Field · remote bonus",
    );
  });
});
