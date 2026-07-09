import ReportContainer from "@components/portal/verifications/ReportContainer";
import DrawerRoutePage from "@components/ui/DrawerRoutePage";
import { ROUTES } from "@lib/routes";

export default async function VerificationReportPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <DrawerRoutePage
      title="Report"
      reference={id}
      fallbackHref={ROUTES.PORTAL.VERIFICATION_DETAIL(id)}
    >
      <div className="p-6">
        <ReportContainer verificationId={id} />
      </div>
    </DrawerRoutePage>
  );
}
