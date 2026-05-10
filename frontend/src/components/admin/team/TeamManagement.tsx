"use client";

import { useState } from "react";
import { Button } from "@3rdparty/ui/button";
import { Input } from "@3rdparty/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@3rdparty/ui/dialog";
import {
  useAdminInvitations,
  useInviteAdminMutation,
  useRevokeInvitationMutation,
} from "../libs/useAdminQueries";
import type {
  AdminSubRole,
  InviteAdminResult,
} from "../libs/admin-service";
import { Copy, MailPlus, RotateCcw } from "lucide-react";
import { getErrorMessage } from "@lib/utils";

const SUB_ROLES: { value: AdminSubRole; label: string; blurb: string }[] = [
  { value: "SUPER", label: "Super Admin", blurb: "Full access. Can invite admins." },
  {
    value: "OPERATIONS",
    label: "Operations Admin",
    blurb: "Approves agents, assigns tasks, releases reports.",
  },
  {
    value: "FINANCE",
    label: "Finance Admin",
    blurb: "Approves payouts, confirms wires, configures pricing.",
  },
];

export default function TeamManagement() {
  const { data, isLoading, refetch } = useAdminInvitations();
  const inviteMutation = useInviteAdminMutation();
  const revokeMutation = useRevokeInvitationMutation();

  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [subRole, setSubRole] = useState<AdminSubRole>("OPERATIONS");
  const [inviteResult, setInviteResult] = useState<InviteAdminResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleInvite = async () => {
    setError(null);
    try {
      const res = await inviteMutation.mutateAsync({ email, subRole });
      setInviteResult(res.data ?? null);
    } catch (e) {
      setError(getErrorMessage(e as Error));
    }
  };

  const handleClose = () => {
    setOpen(false);
    setEmail("");
    setSubRole("OPERATIONS");
    setInviteResult(null);
    setError(null);
    refetch();
  };

  const inviteLink = inviteResult
    ? `${typeof window !== "undefined" ? window.location.origin : ""}/auth/admin-invite/${inviteResult.rawToken}`
    : null;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1
            className="text-3xl font-semibold tracking-tight"
            style={{ color: "var(--brand-navy)", fontFamily: "var(--font-display, Manrope)" }}
          >
            Admin team
          </h1>
          <p className="text-sm mt-1" style={{ color: "var(--brand-on-surface-variant)" }}>
            Invite and manage Veriprops administrators.
          </p>
        </div>
        <Button onClick={() => setOpen(true)}>
          <MailPlus className="w-4 h-4 mr-2" />
          Invite admin
        </Button>
      </div>

      <div
        className="rounded-2xl overflow-hidden"
        style={{
          backgroundColor: "var(--brand-surface-card)",
          boxShadow: "0px 24px 48px rgba(0,13,34,0.06)",
        }}
      >
        <table className="w-full text-sm">
          <thead>
            <tr style={{ backgroundColor: "var(--brand-surface-low)" }}>
              <Th>Email</Th>
              <Th>Role</Th>
              <Th>Status</Th>
              <Th>Sent</Th>
              <Th>Expires</Th>
              <Th className="text-right">Actions</Th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={6} className="text-center py-8" style={{ color: "var(--brand-on-surface-variant)" }}>
                  Loading…
                </td>
              </tr>
            ) : !data?.items?.length ? (
              <tr>
                <td colSpan={6} className="text-center py-8" style={{ color: "var(--brand-on-surface-variant)" }}>
                  No invitations yet.
                </td>
              </tr>
            ) : (
              data.items.map((inv) => (
                <tr key={inv.id} className="border-t" style={{ borderColor: "var(--brand-surface-low)" }}>
                  <Td>{inv.email}</Td>
                  <Td>{inv.subRole}</Td>
                  <Td>
                    <StatusPill status={inv.status} />
                  </Td>
                  <Td>{new Date(inv.createdAt).toLocaleDateString()}</Td>
                  <Td>{new Date(inv.expiresAt).toLocaleDateString()}</Td>
                  <Td className="text-right">
                    {inv.status === "PENDING" && (
                      <button
                        type="button"
                        className="text-xs underline"
                        style={{ color: "var(--destructive)" }}
                        onClick={() => revokeMutation.mutate(inv.id)}
                      >
                        Revoke
                      </button>
                    )}
                  </Td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <Dialog open={open} onOpenChange={(v) => (v ? setOpen(true) : handleClose())}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Invite an admin</DialogTitle>
            <DialogDescription>
              We&apos;ll email a one-time link valid for 72 hours.
            </DialogDescription>
          </DialogHeader>

          {!inviteResult ? (
            <div className="space-y-4">
              <label className="block">
                <span
                  className="text-xs font-medium block mb-1.5"
                  style={{ color: "var(--brand-on-surface-variant)" }}
                >
                  Email
                </span>
                <Input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="admin@veriprops.ng"
                />
              </label>
              <div className="space-y-2">
                <span
                  className="text-xs font-medium block"
                  style={{ color: "var(--brand-on-surface-variant)" }}
                >
                  Role
                </span>
                {SUB_ROLES.map((r) => {
                  const isOn = subRole === r.value;
                  return (
                    <button
                      key={r.value}
                      type="button"
                      onClick={() => setSubRole(r.value)}
                      className="w-full text-left rounded-lg p-3 transition-colors"
                      style={{
                        backgroundColor: isOn
                          ? "var(--brand-viridian-xlight)"
                          : "var(--brand-surface-low)",
                        boxShadow: isOn ? "0 0 0 2px var(--brand-viridian)" : undefined,
                      }}
                    >
                      <div
                        className="font-semibold text-sm"
                        style={{ color: "var(--brand-navy)" }}
                      >
                        {r.label}
                      </div>
                      <div
                        className="text-xs mt-0.5"
                        style={{ color: "var(--brand-on-surface-variant)" }}
                      >
                        {r.blurb}
                      </div>
                    </button>
                  );
                })}
              </div>
              {error && (
                <div
                  className="text-sm rounded-md p-3"
                  style={{
                    color: "var(--destructive)",
                    backgroundColor: "rgba(186,26,26,0.06)",
                  }}
                >
                  {error}
                </div>
              )}
              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={handleClose}
                >
                  Cancel
                </Button>
                <Button
                  type="button"
                  disabled={!email.includes("@") || inviteMutation.isPending}
                  onClick={handleInvite}
                >
                  {inviteMutation.isPending ? "Sending…" : "Send invite"}
                </Button>
              </DialogFooter>
            </div>
          ) : (
            <div className="space-y-4">
              <div
                className="rounded-md p-3 text-xs flex items-center gap-2"
                style={{
                  backgroundColor: "rgba(58,154,106,0.08)",
                  color: "var(--success)",
                }}
              >
                Invitation sent. Share this single-use link if email delivery is delayed.
              </div>
              {inviteLink && (
                <div className="flex gap-2">
                  <Input readOnly value={inviteLink} className="font-mono text-xs" />
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => navigator.clipboard.writeText(inviteLink)}
                  >
                    <Copy className="w-4 h-4" />
                  </Button>
                </div>
              )}
              <DialogFooter>
                <Button type="button" onClick={handleClose}>
                  Done
                </Button>
              </DialogFooter>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

function Th({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <th
      className={`text-xs font-semibold uppercase tracking-wider px-4 py-3 text-left ${className ?? ""}`}
      style={{ color: "var(--brand-on-surface-variant)" }}
    >
      {children}
    </th>
  );
}

function Td({ children, className }: { children: React.ReactNode; className?: string }) {
  return <td className={`px-4 py-3 ${className ?? ""}`}>{children}</td>;
}

function StatusPill({ status }: { status: string }) {
  const map: Record<string, { color: string; bg: string }> = {
    PENDING: { color: "var(--brand-gold)", bg: "var(--brand-gold-xlight)" },
    ACCEPTED: { color: "var(--success)", bg: "rgba(58,154,106,0.08)" },
    EXPIRED: { color: "var(--brand-on-surface-variant)", bg: "var(--brand-surface-low)" },
    REVOKED: { color: "var(--destructive)", bg: "rgba(186,26,26,0.06)" },
  };
  const { color, bg } = map[status] ?? map.PENDING;
  return (
    <span
      className="text-xs font-medium px-2 py-0.5 rounded-full"
      style={{ color, backgroundColor: bg }}
    >
      {status}
    </span>
  );
}

export { RotateCcw };
