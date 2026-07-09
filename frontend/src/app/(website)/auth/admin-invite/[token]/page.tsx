import AdminInviteAcceptContainer from "@components/website/auth/admin-invite/AdminInviteAcceptContainer";

export default async function AdminInvitePage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  return <AdminInviteAcceptContainer token={token} />;
}
