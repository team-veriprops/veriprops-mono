import { Badge } from "@3rdparty/ui/badge";
import { VerificationStatus } from "@/types/verification";
import { humanizeEnumLabel } from "@lib/utils";

type BadgeVariant = "default" | "secondary" | "destructive" | "outline";

// Status → badge variant. The customer-facing label text always comes from the
// backend (statusLabel); this only picks the visual treatment.
const VARIANT: Record<VerificationStatus, BadgeVariant> = {
  [VerificationStatus.DRAFT]: "outline",
  [VerificationStatus.SUBMITTED]: "outline",
  [VerificationStatus.PAYMENT_PENDING]: "outline",
  [VerificationStatus.PAID]: "secondary",
  [VerificationStatus.IN_PROGRESS]: "secondary",
  [VerificationStatus.UNDER_REVIEW]: "secondary",
  [VerificationStatus.COMPLETED]: "default",
  [VerificationStatus.DISPUTED]: "destructive",
  [VerificationStatus.CANCELLED]: "outline",
  [VerificationStatus.FAILED]: "destructive",
  [VerificationStatus.REFUNDED]: "outline",
};

interface Props {
  status: VerificationStatus;
  /** Backend-provided customer label (§9.2). Falls back to a humanized status enum. */
  label?: string;
  className?: string;
}

/** Shared verification status chip (§9.1) — used by the tracking header, the customer list,
 *  and admin surfaces. Customer views pass the backend statusLabel; admin views omit it and
 *  get a humanized enum ("Under Review") rather than the raw "UNDER_REVIEW". */
export function VerificationStatusBadge({ status, label, className }: Props) {
  return (
    <Badge variant={VARIANT[status]} className={className}>
      {label ?? humanizeEnumLabel(status)}
    </Badge>
  );
}
