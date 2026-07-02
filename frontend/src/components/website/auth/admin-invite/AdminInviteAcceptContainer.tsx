"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@3rdparty/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@3rdparty/ui/card";
import { toast } from "@components/3rdparty/ui/use-toast";
import { ROUTES, buildAuthUrl } from "@lib/routes";
import { AuthIntent } from "@components/website/auth/models";
import { InviteAcceptScenario } from "@/types/admin";
import { useCurrentSession } from "@components/website/auth/libs/useAuthQueries";
import {
  useAcceptInvitationMutation,
  useInvitePreviewQuery,
} from "@components/admin/libs/useAdminQueries";

/**
 * Admin invite acceptance (PRD §4.1). Routes the three scenarios:
 * new user → pre-filled signup; existing user → log in to merge; already admin → notice.
 */
export default function AdminInviteAcceptContainer({ token }: { token: string }) {
  const router = useRouter();
  const { data: preview, isLoading, isError } = useInvitePreviewQuery(token);
  const { data: session } = useCurrentSession();
  const accept = useAcceptInvitationMutation();
  const [accepted, setAccepted] = useState(false);

  const acceptRedirect = `${ROUTES.AUTH.GATE}/admin-invite/${token}`;

  if (isLoading) return <Centered>Loading invitation…</Centered>;
  if (isError || !preview) return <Centered>This invitation link is invalid.</Centered>;
  if (preview.expired) return <Centered>This invitation has expired. Ask for a new one.</Centered>;
  if (preview.status !== "PENDING") return <Centered>This invitation has already been used.</Centered>;

  const onAccept = async () => {
    try {
      await accept.mutateAsync(token);
      setAccepted(true);
      toast({ title: "You're now an admin", description: `Role: ${preview.subRole}` });
      router.push(ROUTES.ADMIN.DASHBOARD);
    } catch {
      toast({ title: "Could not accept invitation", variant: "destructive" });
    }
  };

  return (
    <Centered>
      <Card className="w-full max-w-md" data-testid="admin-invite-accept">
        <CardHeader>
          <CardTitle>Admin invitation</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-sm">
          <p>
            You&apos;ve been invited to join Veriprops as an admin (<strong>{preview.subRole}</strong>) for{" "}
            <strong>{preview.email}</strong>.
          </p>

          {preview.scenario === InviteAcceptScenario.ALREADY_ADMIN ? (
            <p className="text-muted-foreground">
              This account is already an admin. No action is needed.
            </p>
          ) : session ? (
            <Button onClick={onAccept} disabled={accept.isPending || accepted} data-testid="admin-invite-accept-btn">
              {accept.isPending ? "Accepting…" : "Accept invitation"}
            </Button>
          ) : preview.scenario === InviteAcceptScenario.NEW_USER ? (
            <Button
              onClick={() =>
                router.push(
                  `${buildAuthUrl(ROUTES.AUTH.SIGNUP, {
                    intent: AuthIntent.INVITED_ADMIN,
                    redirect: acceptRedirect,
                  })}&email=${encodeURIComponent(preview.email)}`,
                )
              }
              data-testid="admin-invite-signup"
            >
              Create your account
            </Button>
          ) : (
            <Button
              onClick={() =>
                router.push(buildAuthUrl(ROUTES.AUTH.LOGIN, { redirect: acceptRedirect }))
              }
              data-testid="admin-invite-login"
            >
              Log in to accept
            </Button>
          )}
        </CardContent>
      </Card>
    </Centered>
  );
}

function Centered({ children }: { children: React.ReactNode }) {
  return <div className="flex min-h-[60vh] items-center justify-center p-4">{children}</div>;
}
