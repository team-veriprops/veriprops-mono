"use client";

import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { Button } from "@3rdparty/ui/button";
import { useAuthStore } from "@components/website/auth/libs/useAuthStore";
import { dashboardFor } from "@components/website/auth/libs/auth/redirect";
import { ROUTES } from "@lib/routes";

/**
 * Ways out of the 403 page. Every 403 in the app lands here — customers and agents as well as
 * admins — so the dashboard link is the visitor's own, and it only appears once the persisted
 * session has rehydrated: before that the server and first client render cannot know who is
 * looking, and must agree.
 */
export default function ForbiddenActions() {
  const hydrated = useAuthStore((s) => s.hydrated);
  const user = useAuthStore((s) => s.session?.user);

  return (
    <>
      {hydrated && user && (
        <Button asChild size="lg" className="w-full sm:w-auto">
          <Link href={dashboardFor(user)}>Go to your dashboard</Link>
        </Button>
      )}
      <Button asChild size="lg" className="w-full sm:w-auto" variant={hydrated && user ? "outline" : "default"}>
        <Link href={ROUTES.HOME}>
          <ArrowLeft aria-hidden />
          Back to home
        </Link>
      </Button>
    </>
  );
}
