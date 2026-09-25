import { Loader2 } from "lucide-react";

/**
 * The post-login hop: `LoginContainer` / `SocialAuthButtons` land here and `proxy.ts` immediately
 * redirects to the dashboard the session's personas earn (step 5, "post-login cleanup"). Nobody
 * stays long enough to act, so this renders progress rather than destinations — a link here could
 * only guess at a persona the proxy already knows.
 */
export default function LoginSuccessPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-brand-surface px-6 py-12">
      <div className="flex flex-col items-center gap-3 text-center">
        <Loader2 className="h-8 w-8 animate-spin text-brand-viridian" aria-hidden />
        <p className="text-sm text-brand-on-surface-variant" role="status">
          Signing you in…
        </p>
      </div>
    </main>
  );
}
