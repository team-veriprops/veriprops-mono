import AdminUserDetail from "@components/admin/users/AdminUserDetail";
import DrawerRoutePage from "@components/ui/DrawerRoutePage";
import { ROUTES } from "@lib/routes";

export default async function AdminUserDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <DrawerRoutePage title="User" reference={id} fallbackHref={ROUTES.ADMIN.USERS}>
      <div className="p-6">
        <AdminUserDetail userId={id} />
      </div>
    </DrawerRoutePage>
  );
}
