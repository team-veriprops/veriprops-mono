import AdminReportReview from "@components/admin/verifications/AdminReportReview";

export default async function AdminReportReviewPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <div className="p-4 sm:p-6">
      <AdminReportReview verificationId={id} />
    </div>
  );
}
