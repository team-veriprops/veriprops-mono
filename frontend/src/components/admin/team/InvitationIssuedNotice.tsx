import { MailCheck, MailWarning } from "lucide-react";
import { CopyText } from "@components/ui/CopyText";
import { AdminInvitationIssued } from "@/types/admin";

interface InvitationIssuedNoticeProps {
  issued: AdminInvitationIssued;
  /** The address the invitation was issued to. */
  email: string;
}

/**
 * What happened to a new admin invitation (§9.1). The backend emails the invitee and says
 * whether that worked. The link is offered in both cases, so a Super Admin can always pass it
 * on by hand, but only a failed email asks them to.
 */
export default function InvitationIssuedNotice({ issued, email }: InvitationIssuedNoticeProps) {
  return (
    <div className="space-y-2 rounded-lg border border-border p-3 text-sm" data-testid="admin-invite-link">
      {issued.emailSent ? (
        <p className="flex items-start gap-2 text-emerald-700" data-testid="admin-invite-emailed">
          <MailCheck className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <span>We emailed the invitation to {email}. You can also share the link below.</span>
        </p>
      ) : (
        <p className="flex items-start gap-2 text-amber-800" data-testid="admin-invite-email-failed">
          <MailWarning className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <span>
            We couldn&apos;t email the invitation to {email}. Copy the link below and send it to them yourself.
          </span>
        </p>
      )}
      <CopyText text={issued.inviteUrl} />
    </div>
  );
}
