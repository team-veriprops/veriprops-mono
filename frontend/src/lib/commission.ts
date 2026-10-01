import { AgentRole } from "@/types/agent";
import { CommissionKind } from "@/types/adminVerification";
import { humanizeEnumLabel } from "@lib/utils";

/**
 * How a commission ledger line is named wherever lines are listed (agent earnings, the admin
 * verification detail): the role, plus "remote bonus" for the bonus an aging pool task paid as
 * its own line beside the fixed commission (§20.1 / D97).
 */
export function commissionLineLabel(line: { role: AgentRole; kind: CommissionKind }): string {
  const role = humanizeEnumLabel(line.role);
  return line.kind === CommissionKind.REMOTE_BONUS ? `${role} · remote bonus` : role;
}
