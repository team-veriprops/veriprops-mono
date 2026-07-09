import TrackingContainer from "@components/portal/verifications/TrackingContainer";
import DrawerRoutePage from "@components/ui/DrawerRoutePage";
import { ROUTES } from "@lib/routes";

export default async function VerificationTrackingPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <DrawerRoutePage title="Verification" reference={id} fallbackHref={ROUTES.PORTAL.VERIFICATIONS}>
      <div className="p-6">
        <TrackingContainer verificationId={id} />
      </div>
    </DrawerRoutePage>
  );
}
