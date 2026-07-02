"use client";

import { useRouter } from "next/navigation";
import { Button } from "@3rdparty/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@3rdparty/ui/card";
import { CopyText } from "@components/ui/CopyText";
import { ROUTES } from "@lib/routes";
import { useVerificationQuery } from "@components/portal/libs/useVerificationQueries";

/** Post-payment confirmation (PRD §5.5): VID, SLA countdown, track CTA. */
export default function ConfirmationContainer({ verificationId }: { verificationId: string }) {
  const router = useRouter();
  const { data: verification, isLoading } = useVerificationQuery(verificationId);

  if (isLoading) return <div className="p-6 text-muted-foreground">Loading…</div>;
  if (!verification) return <div className="p-6">Verification not found.</div>;

  return (
    <div className="mx-auto max-w-xl p-4 sm:p-6" data-testid="verify-confirmed">
      <Card>
        <CardHeader>
          <CardTitle>Payment confirmed 🎉</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-sm">
          <div>
            <p className="text-muted-foreground">Verification ID</p>
            <CopyText text={verification.vid} />
          </div>
          {verification.slaDueDate && (
            <div>
              <p className="text-muted-foreground">Estimated completion</p>
              <p className="font-medium">{new Date(verification.slaDueDate).toLocaleDateString()}</p>
            </div>
          )}
          <Button
            onClick={() => router.push(ROUTES.PORTAL.VERIFICATION_TRACKING(verificationId))}
            data-testid="verify-confirmed-track"
          >
            Track my verification
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
