"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Badge } from "@3rdparty/ui/badge";
import { Button } from "@3rdparty/ui/button";
import { Label } from "@3rdparty/ui/label";
import { Textarea } from "@3rdparty/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@3rdparty/ui/select";
import { AsyncStateComponent } from "@components/ui/AsyncStateComponent";
import { MiniBarBreakdown } from "@components/ui/MiniBarBreakdown";
import { StatusPill } from "@components/ui/StatusPill";
import { formatMinor, humanizeEnumLabel } from "@lib/utils";
import { AdminUserDetail as AdminUserDetailDto } from "@/types/admin";
import {
  AccountStatus,
  TrustStatus,
  UserType,
} from "@components/website/auth/models";
import {
  useAdminUserDetailQuery,
  useForcePasswordResetMutation,
  useReactivateUserMutation,
  useSetTrustStatusMutation,
  useSuspendUserMutation,
} from "@components/admin/libs/useAdminUsersQueries";

const SUSPEND_REASON_MIN_LENGTH = 5;

function InfoRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 py-1.5 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="text-right font-medium text-foreground">{value ?? "—"}</span>
    </div>
  );
}

export default function AdminUserDetail({ userId }: { userId: string }) {
  const { data: user, isLoading, isError } = useAdminUserDetailQuery(userId);

  return (
    <AsyncStateComponent isLoading={isLoading} isError={isError} data={user}>
      {(u) => <UserDetailContent user={u} />}
    </AsyncStateComponent>
  );
}

function UserDetailContent({ user }: { user: AdminUserDetailDto }) {
  const [suspendReason, setSuspendReason] = useState("");
  const [pendingTrust, setPendingTrust] = useState<TrustStatus>(user.trustStatus);

  const suspend = useSuspendUserMutation();
  const reactivate = useReactivateUserMutation();
  const forceReset = useForcePasswordResetMutation();
  const setTrust = useSetTrustStatusMutation();

  const isSuspended = user.accountStatus === AccountStatus.SUSPENDED;
  const isAdmin = user.userType === UserType.ADMIN;

  const onSuspend = () => {
    const reason = suspendReason.trim();
    if (reason.length < SUSPEND_REASON_MIN_LENGTH) {
      toast.error("Provide a suspension reason first.");
      return;
    }
    suspend.mutate(
      { userId: user.id, reason },
      {
        onSuccess: () => {
          toast.success("Account suspended");
          setSuspendReason("");
        },
        onError: () => toast.error("Could not suspend the account."),
      },
    );
  };

  const onReactivate = () => {
    reactivate.mutate(user.id, {
      onSuccess: () => toast.success("Account reactivated"),
      onError: () => toast.error("Could not reactivate the account."),
    });
  };

  const onForceReset = () => {
    forceReset.mutate(user.id, {
      onSuccess: () => toast.success("Password reset email sent; all sessions revoked."),
      onError: () => toast.error("Could not force the password reset."),
    });
  };

  const onSaveTrust = () => {
    setTrust.mutate(
      { userId: user.id, trustStatus: pendingTrust },
      {
        onSuccess: () => toast.success("Trust status updated"),
        onError: () => toast.error("Could not update the trust status."),
      },
    );
  };

  return (
    <div className="space-y-8" data-testid="admin-user-detail">
      {/* ── Profile ─────────────────────────────────────────── */}
      <section className="space-y-1">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Profile
        </h2>
        <InfoRow
          label="Email"
          value={
            <span>
              {user.email}{" "}
              {user.emailVerified && <Badge variant="secondary">Verified</Badge>}
            </span>
          }
        />
        <InfoRow
          label="Phone"
          value={
            <span>
              +{user.phoneDialCode} {user.phone}{" "}
              {user.phoneVerified && <Badge variant="secondary">Verified</Badge>}
            </span>
          }
        />
        <InfoRow label="Country" value={user.countryOfResidence} />
        <InfoRow label="Timezone" value={user.timezone} />
        <InfoRow label="Currency" value={user.preferredCurrency} />
        <InfoRow label="Joined" value={new Date(user.dateCreated).toLocaleString()} />
        <InfoRow
          label="Personas"
          value={
            user.personas.length
              ? user.personas.map((p) => (
                  <Badge key={p} variant="secondary" className="ml-1">
                    {humanizeEnumLabel(p)}
                  </Badge>
                ))
              : "—"
          }
        />
        <InfoRow label="Type" value={humanizeEnumLabel(user.userType)} />
        {user.adminSubRole && (
          <InfoRow label="Admin sub-role" value={humanizeEnumLabel(user.adminSubRole)} />
        )}
      </section>

      {/* ── Account standing ────────────────────────────────── */}
      <section className="space-y-1">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Account standing
        </h2>
        <InfoRow label="Account status" value={<StatusPill status={user.accountStatus} />} />
        {isSuspended && (
          <>
            <InfoRow
              label="Suspended at"
              value={user.suspendedAt ? new Date(user.suspendedAt).toLocaleString() : "—"}
            />
            <InfoRow label="Reason" value={user.suspensionReason} />
          </>
        )}
        <InfoRow label="Trust status" value={<StatusPill status={user.trustStatus} />} />
        <InfoRow label="Referral credit" value={formatMinor(user.creditBalanceKobo)} />
        {user.referredBy && <InfoRow label="Referred by" value={user.referredBy} />}
      </section>

      {/* ── Activity ────────────────────────────────────────── */}
      <section className="space-y-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Activity
        </h2>
        <InfoRow label="Verifications" value={user.verificationsTotal} />
        <InfoRow label="Payments" value={user.paymentsCount} />
        {user.verificationsTotal > 0 && (
          <MiniBarBreakdown counts={user.verificationCounts} />
        )}
      </section>

      {/* ── Recent security events ──────────────────────────── */}
      <section className="space-y-2">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Recent security events
        </h2>
        {user.recentSecurityEvents.length === 0 ? (
          <p className="text-sm text-muted-foreground">No recent security events.</p>
        ) : (
          <ul className="space-y-1">
            {user.recentSecurityEvents.map((e) => (
              <li
                key={e.id}
                className="flex items-center justify-between gap-4 rounded border border-border p-2 text-sm"
              >
                <span>
                  <span className="font-medium">{humanizeEnumLabel(e.type)}</span>{" "}
                  <span className="text-muted-foreground">— {e.description}</span>
                </span>
                <span className="shrink-0 text-xs text-muted-foreground">
                  {new Date(e.occurredAt).toLocaleString()}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* ── Admin actions ───────────────────────────────────── */}
      <section className="space-y-4 border-t border-border pt-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Actions
        </h2>

        <div className="space-y-2">
          <Label>Trust status</Label>
          <div className="flex items-center gap-2">
            <Select
              value={pendingTrust}
              onValueChange={(v) => setPendingTrust(v as TrustStatus)}
            >
              <SelectTrigger className="w-48" data-testid="admin-user-trust-select">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {Object.values(TrustStatus).map((t) => (
                  <SelectItem key={t} value={t}>
                    {humanizeEnumLabel(t)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button
              onClick={onSaveTrust}
              disabled={setTrust.isPending || pendingTrust === user.trustStatus}
              data-testid="admin-user-save-trust"
            >
              Save
            </Button>
          </div>
        </div>

        <div className="space-y-2">
          <Button
            variant="outline"
            onClick={onForceReset}
            disabled={forceReset.isPending || isSuspended}
            data-testid="admin-user-force-reset"
          >
            {forceReset.isPending ? "Sending…" : "Force password reset"}
          </Button>
          <p className="text-xs text-muted-foreground">
            Emails a reset link and signs the user out of every device.
          </p>
        </div>

        {isAdmin ? (
          <p className="text-sm text-muted-foreground">
            Admin accounts are managed from the Admin Team page (deactivation), not suspension.
          </p>
        ) : isSuspended ? (
          <div className="space-y-2">
            <Button
              onClick={onReactivate}
              disabled={reactivate.isPending}
              data-testid="admin-user-reactivate"
            >
              {reactivate.isPending ? "Reactivating…" : "Reactivate account"}
            </Button>
          </div>
        ) : (
          <div className="space-y-2">
            <Label>Suspend account</Label>
            <Textarea
              value={suspendReason}
              onChange={(e) => setSuspendReason(e.target.value)}
              placeholder="Reason (required, admin-internal — recorded in the audit log)"
              data-testid="admin-user-suspend-reason"
            />
            <Button
              variant="destructive"
              onClick={onSuspend}
              disabled={suspend.isPending || suspendReason.trim().length < SUSPEND_REASON_MIN_LENGTH}
              data-testid="admin-user-suspend"
            >
              {suspend.isPending ? "Suspending…" : "Suspend account"}
            </Button>
            <p className="text-xs text-muted-foreground">
              Suspension blocks sign-in and revokes all active sessions immediately.
            </p>
          </div>
        )}
      </section>
    </div>
  );
}
