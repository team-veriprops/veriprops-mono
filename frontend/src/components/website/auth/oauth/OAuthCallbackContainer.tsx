"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { Loader2, AlertTriangle, Mail } from "lucide-react";
import AuthShell from "../AuthShell";
import AuthHeading from "../AuthHeading";
import { Button } from "@3rdparty/ui/button";
import { useCurrentSession } from "../libs/useAuthQueries";
import ProfileCompletionModal from "./ProfileCompletionModal";
import { ROUTES, isAuthIntent, buildAuthUrl } from "@lib/routes";
import { resolvePostAuthRedirect } from "@components/website/auth/libs/auth/redirect";

interface Props {
  provider: string;
}

export default function OAuthCallbackContainer({ provider }: Props) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const intentParam = searchParams.get("intent");
  const intent = isAuthIntent(intentParam) ? intentParam : "default";
  const errorCode = searchParams.get("error");
  const collisionEmail = searchParams.get("collision_email");

  const sessionQuery = useCurrentSession(!errorCode && !collisionEmail);
  const [showProfileModal, setShowProfileModal] = useState(false);

  const user = sessionQuery.data?.user;
  const profileIncomplete = useMemo(() => {
    if (!user) return false;
    return (
      !user.phoneVerified ||
      !user.countryOfResidence ||
      !user.timezone ||
      !user.preferredCurrency
    );
  }, [user]);

  useEffect(() => {
    if (errorCode || collisionEmail) return;
    if (!user) return;
    if (profileIncomplete) {
      setShowProfileModal(true);
    } else {
      router.replace(resolvePostAuthRedirect(user, { intent }));
    }
  }, [user, profileIncomplete, errorCode, collisionEmail, router, intent]);

  if (errorCode) {
    return (
      <AuthShell>
        <AuthHeading
          eyebrow="Sign-in failed"
          title="We couldn't sign you in."
          subtitle={`Provider ${provider} reported an error. You can try again or sign in with email.`}
        />
        <div
          className="p-4 rounded-xl flex items-start gap-3 mb-6"
          style={{
            backgroundColor: "rgba(186,26,26,0.06)",
            border: "1px solid rgba(186,26,26,0.18)",
            color: "var(--danger)",
          }}
        >
          <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
          <div className="text-sm leading-relaxed">
            <strong className="block">Error code: {errorCode}</strong>
            If this keeps happening, please contact support.
          </div>
        </div>
        <div className="flex gap-3">
          <Link href={ROUTES.AUTH.LOGIN} className="flex-1">
            <Button variant="outline" className="w-full" size="lg">
              Sign in with email
            </Button>
          </Link>
          <Link href={buildAuthUrl(ROUTES.AUTH.GATE, { intent })} className="flex-1">
            <Button className="w-full" size="lg">
              Try again
            </Button>
          </Link>
        </div>
      </AuthShell>
    );
  }

  if (collisionEmail) {
    return (
      <AuthShell>
        <AuthHeading
          eyebrow="Account already exists"
          title="That email is already registered."
          subtitle="Sign in with your password — once you're in, you can link your social account from Account → Linked accounts."
        />
        <div
          className="p-4 rounded-xl flex items-start gap-3 mb-6"
          style={{
            backgroundColor: "rgba(0,13,34,0.04)",
            border: "1px solid rgba(196,198,207,0.4)",
          }}
        >
          <Mail className="w-5 h-5 shrink-0 mt-0.5" style={{ color: "var(--brand-viridian)" }} />
          <div className="text-sm leading-relaxed" style={{ color: "var(--brand-on-surface)" }}>
            We found an existing account for{" "}
            <strong>{collisionEmail}</strong>. Sign in with your password to continue.
          </div>
        </div>
        <Link
          href={`${ROUTES.AUTH.LOGIN}?email=${encodeURIComponent(collisionEmail)}&link=${provider}`}
        >
          <Button className="w-full" size="lg">
            Sign in with password and link {provider}
          </Button>
        </Link>
      </AuthShell>
    );
  }

  return (
    <>
      <AuthShell>
        <AuthHeading
          eyebrow="Almost there"
          title="Signing you in."
          subtitle="Just a moment — we're finalising your session."
        />
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin" style={{ color: "var(--brand-viridian)" }} />
        </div>
      </AuthShell>
      <ProfileCompletionModal
        open={showProfileModal && !!user}
        user={user}
        intent={intent}
        onComplete={() => {
          if (user) router.replace(resolvePostAuthRedirect(user, { intent }));
        }}
      />
    </>
  );
}
