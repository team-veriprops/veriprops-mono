import AdminVerificationDetail from "@components/admin/verifications/AdminVerificationDetail";

export default async function AdminVerificationDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <div className="p-4 sm:p-6">
      <AdminVerificationDetail verificationId={id} />
    </div>
  );
}
