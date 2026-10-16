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
import { toast } from "sonner";
import { Column, DataTable, TableFilterUpdate } from "@components/ui/table/DataTable";
import InvitationIssuedNotice from "./InvitationIssuedNotice";
import DetailDrawer, { DetailDrawerWidth } from "@components/ui/DetailDrawer";
import { useSyncedQueryState } from "@hooks/useSyncedQueryState";
import { useGlobalSettings } from "@stores/useGlobalSettings";
import { humanizeEnumLabel } from "@lib/utils";
import { emptyPage, Page } from "@/types/models";
import { AdminInvitationIssued, AdminInvitationStatus, AdminMember, AdminSubRole } from "@/types/admin";
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

// Keys are the backend's sortable fields: "Name" sorts by first name, "Role" by the sub-role.
const columns: Column<AdminMember & Record<string, unknown>>[] = [
  { key: "firstName", label: "Name", render: (_v, item) => item.name },
  { key: "email", label: "Email" },
  {
    key: "adminSubRole",
    label: "Role",
    render: (_v, item) => <Badge>{item.subRole ? humanizeEnumLabel(item.subRole) : "—"}</Badge>,
  },
];

interface TeamTableState extends Record<string, unknown> {
  page: number;
  query: string;
  subRole: string;
  orderBy: string;
}

export default function AdminTeamManagement() {
  const [tableState, updateTableState] = useSyncedQueryState<TeamTableState>({
    page: 0,
    query: "",
    subRole: "",
    orderBy: "",
  });
  const page = tableState.page ?? 0;
  const query = tableState.query ?? "";
  const subRole = tableState.subRole ?? "";
  const orderBy = tableState.orderBy ?? "";
  const pageSize = useGlobalSettings((s) => s.settings.rowsPerPage);

  const [selected, setSelected] = useState<AdminMember | null>(null);
  const [inviteOpen, setInviteOpen] = useState(false);
  const [inviteFirstName, setInviteFirstName] = useState("");
  const [inviteLastName, setInviteLastName] = useState("");
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<AdminSubRole>(AdminSubRole.OPERATIONS);
  const [issued, setIssued] = useState<{ invitation: AdminInvitationIssued; email: string } | null>(null);
  const [pendingRole, setPendingRole] = useState<AdminSubRole | undefined>();

  const { data: team, isLoading, isError, error } = useAdminTeamQuery(page, pageSize, query, subRole, orderBy);
  const { data: invitations } = useAdminInvitationsQuery(0, pageSize);
  const invite = useInviteAdminMutation();
  const revoke = useRevokeInvitationMutation();
  const changeRole = useChangeSubRoleMutation();
  const deactivate = useDeactivateMemberMutation();

  const dataPage = (team ?? emptyPage(page, pageSize)) as Page<AdminMember & Record<string, unknown>>;

  const updateFilters = (u: TableFilterUpdate) => {
    updateTableState(u as Partial<TeamTableState>);
  };

  const onInvite = async () => {
    const res = await invite.mutateAsync({
      email: inviteEmail,
      subRole: inviteRole,
      firstName: inviteFirstName.trim() || undefined,
      lastName: inviteLastName.trim() || undefined,
    });
    const invitation = res.data;
    setIssued(invitation ? { invitation, email: inviteEmail } : null);
    setInviteFirstName("");
    setInviteLastName("");
    setInviteEmail("");
    if (invitation?.emailSent) {
      toast.success("Invitation sent", { description: `We emailed the invitation to ${inviteEmail}.` });
    } else {
      toast.warning("Invitation created, but not emailed", {
        description: "Copy the link and send it to the invitee yourself.",
      });
    }
  };

  const closeInvite = () => {
    setInviteOpen(false);
    setIssued(null);
  };

  const onChangeRole = async () => {
    if (!selected || !pendingRole) return;
    await changeRole.mutateAsync({ userId: selected.id, subRole: pendingRole });
    toast.success("Role updated");
    setSelected(null);
    setPendingRole(undefined);
  };

  const onDeactivate = async () => {
    if (!selected) return;
    await deactivate.mutateAsync(selected.id);
    toast.success("Admin deactivated");
    setSelected(null);
  };

  return (
    <div className="space-y-6" data-testid="admin-team">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-foreground">Admin team</h1>
        <Button onClick={() => setInviteOpen(true)} data-testid="admin-invite-toggle">
          Invite admin
        </Button>
      </div>

      <DetailDrawer
        open={inviteOpen}
        onOpenChange={(o) => (o ? setInviteOpen(true) : closeInvite())}
        title="Invite a new admin"
        reference="Admin team"
        drawerWidth={DetailDrawerWidth.SMALL}
      >
        <div className="space-y-4 p-6" data-testid="admin-invite-form">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>First name</Label>
              <Input
                value={inviteFirstName}
                onChange={(e) => setInviteFirstName(e.target.value)}
                data-testid="admin-invite-first-name"
              />
            </div>
            <div className="space-y-2">
              <Label>Last name</Label>
              <Input
                value={inviteLastName}
                onChange={(e) => setInviteLastName(e.target.value)}
                data-testid="admin-invite-last-name"
              />
            </div>
          </div>
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
                    {humanizeEnumLabel(r)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button
            onClick={onInvite}
            disabled={invite.isPending || !inviteEmail}
            data-testid="admin-invite-submit"
          >
            {invite.isPending ? "Creating…" : "Create invitation"}
          </Button>
          {issued && <InvitationIssuedNotice issued={issued.invitation} email={issued.email} />}
        </div>
      </DetailDrawer>

      <DataTable<AdminMember & Record<string, unknown>>
        dataPage={dataPage}
        columns={columns}
        currentPage={page}
        orderBy={orderBy || undefined}
        updateFilters={updateFilters}
        searchValue={query}
        filters={[
          {
            key: "subRole",
            label: "Role",
            value: subRole,
            options: ASSIGNABLE_ROLES.map((r) => ({ label: humanizeEnumLabel(r), value: r })),
          },
        ]}
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
                  {[inv.firstName, inv.lastName].filter(Boolean).join(" ") &&
                    `${[inv.firstName, inv.lastName].filter(Boolean).join(" ")} · `}
                  {inv.email} — <Badge variant="secondary">{humanizeEnumLabel(inv.subRole)}</Badge>{" "}
                  <span className="text-muted-foreground">({humanizeEnumLabel(inv.status)})</span>
                </span>
                {inv.status === AdminInvitationStatus.PENDING && (
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
                      {humanizeEnumLabel(r)}
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
