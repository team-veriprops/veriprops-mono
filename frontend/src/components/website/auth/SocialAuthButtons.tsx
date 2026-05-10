"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { startOauthPopup } from "./libs/auth/oauthPopup";
import { useCurrentSession } from "./libs/useAuthQueries";
import { OAuthFlowMode, SocialProvider } from "@components/website/auth/models";
import { resolvePostAuthRedirect } from "./libs/auth/redirect";
import { AuthIntent, isAuthIntent, ROUTES } from "@lib/routes";

interface SocialAuthButtonsProps {
  /** Hint text — "Sign in with" or "Sign up with". */
  verb?: "Continue with" | "Sign in with" | "Sign up with";
  intent?: AuthIntent | null;
  className?: string;
}

const oauthEnv = (provider: SocialProvider): boolean => {
  // Default-on so dev environments without env config still see the buttons.
  // Production deployments can switch a provider off via env without a code
  // change (e.g. while waiting for Apple Developer Program approval).
  if (provider === SocialProvider.GOOGLE) return process.env.NEXT_PUBLIC_OAUTH_GOOGLE_DISABLED !== "true";
  if (provider === SocialProvider.APPLE) return process.env.NEXT_PUBLIC_OAUTH_APPLE_DISABLED !== "true";
  if (provider === SocialProvider.FACEBOOK) return process.env.NEXT_PUBLIC_OAUTH_FACEBOOK_DISABLED !== "true";
  return false;
};

const GoogleGlyph = () => (
  <svg viewBox="0 0 24 24" className="w-4 h-4" aria-hidden>
    <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.56c2.08-1.92 3.28-4.74 3.28-8.1Z"/>
    <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.65l-3.56-2.77c-.99.66-2.25 1.06-3.72 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84A11 11 0 0 0 12 23Z"/>
    <path fill="#FBBC05" d="M5.84 14.11A6.6 6.6 0 0 1 5.5 12c0-.73.13-1.44.34-2.11V7.05H2.18A11 11 0 0 0 1 12c0 1.78.43 3.46 1.18 4.95l3.66-2.84Z"/>
    <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1A11 11 0 0 0 2.18 7.05l3.66 2.84C6.71 7.31 9.14 5.38 12 5.38Z"/>
  </svg>
);

const AppleGlyph = () => (
  <svg viewBox="0 0 24 24" className="w-4 h-4" aria-hidden fill="currentColor">
    <path d="M16.365 1.43c0 1.14-.473 2.28-1.245 3.087-.83.872-2.16 1.55-3.224 1.43-.135-1.14.435-2.32 1.222-3.087.835-.873 2.273-1.55 3.247-1.43Zm3.532 17.39c-.7 1.04-1.45 2.07-2.62 2.09-1.16.02-1.5-.69-3.16-.69-1.66 0-2.04.66-3.13.71-1.13.05-1.99-1.13-2.7-2.16-2.16-3.13-3.81-8.86-1.59-12.74 1.1-1.92 3.07-3.13 5.21-3.16 1.13-.02 2.2.76 2.89.76.69 0 2.09-.94 3.53-.8.6.02 2.27.24 3.34 1.85-2.71 1.46-2.27 5.13.34 6.4-.4 1.21-1.05 2.42-1.97 3.74Z"/>
  </svg>
);

const FacebookGlyph = () => (
  <svg viewBox="0 0 24 24" className="w-4 h-4" aria-hidden>
    <path fill="#1877F2" d="M24 12c0-6.627-5.373-12-12-12S0 5.373 0 12c0 5.99 4.388 10.954 10.125 11.854V15.47H7.078V12h3.047V9.356c0-3.007 1.792-4.668 4.533-4.668 1.312 0 2.686.234 2.686.234v2.953h-1.514c-1.491 0-1.956.926-1.956 1.875V12h3.328l-.532 3.47h-2.796v8.385C19.612 22.954 24 17.99 24 12Z"/>
    <path fill="#FFF" d="m16.671 15.47.532-3.47H13.875V9.75c0-.949.465-1.875 1.956-1.875h1.514V4.922s-1.374-.234-2.686-.234c-2.741 0-4.533 1.661-4.533 4.668V12H7.078v3.47h3.047v8.385a12.06 12.06 0 0 0 3.75 0V15.47h2.796Z"/>
  </svg>
);

interface ProviderConfig {
  provider: SocialProvider;
  label: string;
  glyph: React.ReactNode;
  brandStyle: React.CSSProperties;
}

const PROVIDERS: ProviderConfig[] = [
  {
    provider: SocialProvider.GOOGLE,
    label: "Google",
    glyph: <GoogleGlyph />,
    brandStyle: {
      backgroundColor: "var(--brand-surface-card)",
      color: "var(--brand-navy)",
      border: "1px solid rgba(196,198,207,0.4)",
      boxShadow: "0 1px 2px rgba(0,13,34,0.04)",
    },
  },
  {
    provider: SocialProvider.APPLE,
    label: "Apple",
    glyph: <AppleGlyph />,
    brandStyle: {
      backgroundColor: "#000",
      color: "#fff",
      border: "1px solid #000",
    },
  },
  {
    provider: SocialProvider.FACEBOOK,
    label: "Facebook",
    glyph: <FacebookGlyph />,
    brandStyle: {
      backgroundColor: "var(--brand-surface-card)",
      color: "var(--brand-navy)",
      border: "1px solid rgba(196,198,207,0.4)",
      boxShadow: "0 1px 2px rgba(0,13,34,0.04)",
    },
  },
];

export default function SocialAuthButtons({
  verb = "Continue with",
  intent,
  className,
}: SocialAuthButtonsProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const sessionQuery = useCurrentSession(false);
  const redirect = searchParams.get("redirect");
  const intentParam = searchParams.get("intent");
  const resolvedIntent: AuthIntent | null = intent ?? (isAuthIntent(intentParam) ? intentParam : null);

  const [pendingProvider, setPendingProvider] = useState<SocialProvider | null>(null);
  const [popupBlockedUrl, setPopupBlockedUrl] = useState<string | null>(null);

  const handleClick = (provider: SocialProvider) => {
    if (typeof window === "undefined") return;
    setPendingProvider(provider);
    setPopupBlockedUrl(null);

    startOauthPopup(provider, {
      intent: resolvedIntent ?? undefined,
      mode: OAuthFlowMode.AUTH,
      onSuccess: async () => {
        setPendingProvider(null);
        try {
          const res = await sessionQuery.refetch();
          const user = res.data?.user;
          const dest = user
            ? resolvePostAuthRedirect(user, { intent: resolvedIntent, redirect })
            : ROUTES.AUTH.LOGIN_SUCCESS_REDIRECT;
          router.replace(dest);
        } catch {
          router.replace(ROUTES.AUTH.LOGIN_SUCCESS_REDIRECT);
        }
      },
      onCancel: () => {
        setPendingProvider(null);
      },
      onError: (err) => {
        setPendingProvider(null);
        if (err.code === "popup_blocked") {
          setPopupBlockedUrl(err.authorizationUrl ?? null);
          toast.error("Popup blocked. Allow popups, or use the link below to continue.");
          return;
        }
        if (err.code === "timeout") {
          toast.error("Sign-in timed out. Please try again.");
          return;
        }
        toast.error(err.message ?? "Login failed. Please try another method.");
      },
    });
  };

  const visible = PROVIDERS.filter((p) => oauthEnv(p.provider));
  if (visible.length === 0) return null;

  return (
    <div className={className}>
      <div className="grid grid-cols-1 gap-3">
        {visible.map(({ provider, label, glyph, brandStyle }) => (
          <button
            key={provider}
            type="button"
            onClick={() => handleClick(provider)}
            disabled={pendingProvider !== null}
            className="group inline-flex items-center justify-center gap-2.5 px-4 py-3 rounded-lg text-sm font-semibold transition-all duration-150 disabled:opacity-60"
            style={brandStyle}
            data-testid={`oauth-${provider.toLowerCase()}`}
          >
            {glyph}
            {pendingProvider === provider ? "Opening…" : `${verb} ${label}`}
          </button>
        ))}
      </div>

      {popupBlockedUrl && (
        <p className="mt-3 text-xs text-center" style={{ color: "var(--brand-on-surface-variant)" }}>
          Popups are blocked.{" "}
          <a
            href={popupBlockedUrl}
            className="font-semibold underline"
            style={{ color: "var(--brand-viridian)" }}
          >
            Continue here →
          </a>
        </p>
      )}
    </div>
  );
}

export function AuthDivider({ label = "or" }: { label?: string }) {
  return (
    <div className="my-6 flex items-center gap-4" aria-hidden>
      <span className="flex-1 h-px bg-[var(--brand-surface-high)]" />
      <span
        className="text-xs uppercase tracking-widest font-semibold"
        style={{ color: "var(--brand-on-surface-variant)" }}
      >
        {label}
      </span>
      <span className="flex-1 h-px bg-[var(--brand-surface-high)]" />
    </div>
  );
}
