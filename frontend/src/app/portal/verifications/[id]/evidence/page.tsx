import EvidenceContainer from "@components/portal/verifications/EvidenceContainer";
import DrawerRoutePage from "@components/ui/DrawerRoutePage";
import { ROUTES } from "@lib/routes";

export default async function VerificationEvidencePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <DrawerRoutePage
      title="Evidence"
      reference={id}
      fallbackHref={ROUTES.PORTAL.VERIFICATION_DETAIL(id)}
    >
      <div className="p-6">
        <EvidenceContainer verificationId={id} />
      </div>
    </DrawerRoutePage>
  );
}
