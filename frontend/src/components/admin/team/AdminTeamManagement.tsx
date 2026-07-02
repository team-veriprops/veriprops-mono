"use client";

import { useState } from "react";
import { Badge } from "@3rdparty/ui/badge";
import { Button } from "@3rdparty/ui/button";
import { Input } from "@3rdparty/ui/input";
import { Label } from "@3rdparty/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@3rdparty/ui/select";
import { Card, CardContent, CardHeader, CardTitle } from "@3rdparty/ui/card";
import { toast } from "@components/3rdparty/ui/use-toast";
import { CopyText } from "@components/ui/CopyText";
import { Column, DataTable } from "@components/ui/table/DataTable";
import DetailDrawer, { DetailDrawerWidth } from "@components/ui/DetailDrawer";
import { Page, PageRequest } from "@/types/models";
import { AdminMember, AdminSubRole } from "@/types/admin";
import {
  useAdminInvitationsQuery,
  useAdminTeamQuery,
  useChangeSubRoleMutation,
  useDeactivateMemberMutation,
  useInviteAdminMutation,
  useRevokeInvitationMutation,
} from "@components/admin/libs/useAdminQueries";

// Sub-roles a Super Admin may assign (content roles are managed elsewhere).
const ASSIGNABLE_ROLES = [AdminSubRole.OPERATIONS, AdminSubRole.FINANCE, AdminSubRole.SUPER];

const columns: Column<AdminMember & Record<string, unknown>>[] = [
  { key: "name", label: "Name" },
  { key: "email", label: "Email" },
  {
    key: "subRole",
    label: "Role",
    render: (_v, item) => <Badge>{item.subRole ?? "—"}</Badge>,
  },
];

const PAGE_SIZE = 10;

export default function AdminTeamManagement() {
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<AdminMember | null>(null);
  const [inviteOpen, setInviteOpen] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<AdminSubRole>(AdminSubRole.OPERATIONS);
  const [inviteUrl, setInviteUrl] = useState<string | null>(null);
  const [pendingRole, setPendingRole] = useState<AdminSubRole | undefined>();

  const { data: team, isLoading, isError, error } = useAdminTeamQuery(page, PAGE_SIZE);
  const { data: invitations } = useAdminInvitationsQuery(0, PAGE_SIZE);
  const invite = useInviteAdminMutation();
  const revoke = useRevokeInvitationMutation();
  const changeRole = useChangeSubRoleMutation();
  const deactivate = useDeactivateMemberMutation();

  const totalPages = team ? Math.max(1, Math.ceil(team.total / PAGE_SIZE)) : 0;
  const dataPage: Page<AdminMember & Record<string, unknown>> = {
    status: "success",
    code: "200",
    items: (team?.items ?? []) as (AdminMember & Record<string, unknown>)[],
    meta: {
      page,
      pageSize: PAGE_SIZE,
      count: team?.items.length ?? 0,
      total: team?.total ?? 0,
      totalPages,
      prevPage: page > 0 ? page - 1 : undefined,
      nextPage: page + 1 < totalPages ? page + 1 : undefined,
    },
  };

  const updateFilters = (u: Partial<PageRequest>) => {
    if (u.page !== undefined) setPage(u.page);
  };

  const onInvite = async () => {
    const res = await invite.mutateAsync({ email: inviteEmail, subRole: inviteRole });
    setInviteUrl(res.data?.inviteUrl ?? null);
    setInviteEmail("");
    toast({ title: "Invitation created", description: "Share the link with the invitee." });
  };

  const onChangeRole = async () => {
    if (!selected || !pendingRole) return;
    await changeRole.mutateAsync({ userId: selected.id, subRole: pendingRole });
    toast({ title: "Role updated" });
    setSelected(null);
    setPendingRole(undefined);
  };

  const onDeactivate = async () => {
    if (!selected) return;
    await deactivate.mutateAsync(selected.id);
    toast({ title: "Admin deactivated" });
    setSelected(null);
  };

  return (
    <div className="space-y-6" data-testid="admin-team">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-foreground">Admin team</h1>
        <Button onClick={() => setInviteOpen((o) => !o)} data-testid="admin-invite-toggle">
          Invite admin
        </Button>
      </div>

      {inviteOpen && (
        <Card>
          <CardHeader>
            <CardTitle>Invite a new admin</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label>Email</Label>
                <Input
                  type="email"
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  data-testid="admin-invite-email"
                />
              </div>
              <div className="space-y-2">
                <Label>Sub-role</Label>
                <Select value={inviteRole} onValueChange={(v) => setInviteRole(v as AdminSubRole)}>
                  <SelectTrigger data-testid="admin-invite-role">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {ASSIGNABLE_ROLES.map((r) => (
                      <SelectItem key={r} value={r}>
                        {r}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <Button
              onClick={onInvite}
              disabled={invite.isPending || !inviteEmail}
              data-testid="admin-invite-submit"
            >
              {invite.isPending ? "Creating…" : "Create invitation"}
            </Button>
            {inviteUrl && (
              <div className="rounded-lg border border-border p-3 text-sm">
                <p className="mb-1 text-muted-foreground">Invitation link (share with the invitee):</p>
                <CopyText text={inviteUrl} />
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <DataTable<AdminMember & Record<string, unknown>>
        dataPage={dataPage}
        columns={columns}
        currentPage={page}
        updateFilters={updateFilters}
        isLoading={isLoading}
        isError={isError}
        error={error as Error | null}
        isRowClickable
        onRowClick={(row) => {
          setSelected(row);
          setPendingRole(row.subRole);
        }}
        searchPlaceholder="Search admins…"
      />

      {invitations?.data && invitations.data.items.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Pending invitations</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {invitations.data.items.map((inv) => (
              <div
                key={inv.id}
                className="flex items-center justify-between rounded border border-border p-2 text-sm"
              >
                <span>
                  {inv.email} — <Badge variant="secondary">{inv.subRole}</Badge>{" "}
                  <span className="text-muted-foreground">({inv.status})</span>
                </span>
                {inv.status === "PENDING" && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => revoke.mutate(inv.id)}
                    data-testid="admin-invite-revoke"
                  >
                    Revoke
                  </Button>
                )}
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      <DetailDrawer
        open={!!selected}
        onOpenChange={(o) => !o && setSelected(null)}
        title={selected?.name ?? "Admin"}
        reference={selected?.email ?? ""}
        drawerWidth={DetailDrawerWidth.SMALL}
      >
        {selected && (
          <div className="space-y-6 p-6" data-testid="admin-team-detail">
            <div className="space-y-2">
              <Label>Sub-role</Label>
              <Select value={pendingRole} onValueChange={(v) => setPendingRole(v as AdminSubRole)}>
                <SelectTrigger data-testid="admin-team-role-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ASSIGNABLE_ROLES.map((r) => (
                    <SelectItem key={r} value={r}>
                      {r}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button
                onClick={onChangeRole}
                disabled={changeRole.isPending || pendingRole === selected.subRole}
                data-testid="admin-team-save-role"
              >
                Save role
              </Button>
            </div>

            <div className="border-t border-border pt-4">
              <Button
                variant="destructive"
                onClick={onDeactivate}
                disabled={deactivate.isPending}
                data-testid="admin-team-deactivate"
              >
                Deactivate admin
              </Button>
            </div>
          </div>
        )}
      </DetailDrawer>
    </div>
  );
}
