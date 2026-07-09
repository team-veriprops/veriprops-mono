import AdminVerificationDetail from "@components/admin/verifications/AdminVerificationDetail";
import DrawerRoutePage from "@components/ui/DrawerRoutePage";
import { ROUTES } from "@lib/routes";

export default async function AdminVerificationDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <DrawerRoutePage title="Verification" reference={id} fallbackHref={ROUTES.ADMIN.VERIFICATIONS}>
      <div className="p-6">
        <AdminVerificationDetail verificationId={id} />
      </div>
    </DrawerRoutePage>
  );
}
