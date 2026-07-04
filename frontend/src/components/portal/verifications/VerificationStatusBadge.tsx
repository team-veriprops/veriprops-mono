import { Badge } from "@3rdparty/ui/badge";
import { VerificationStatus } from "@/types/verification";

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
  /** Backend-provided customer label (§9.2). Falls back to the raw status. */
  label?: string;
  className?: string;
}

/** Shared verification status chip (§9.1) — used by the tracking header and the list. */
export function VerificationStatusBadge({ status, label, className }: Props) {
  return (
    <Badge variant={VARIANT[status]} className={className}>
      {label ?? status}
    </Badge>
  );
}
