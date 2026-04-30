"use client";

import { authService } from "./libs/useAuthQueries";
import { SocialProvider } from "@components/website/auth/models";
import { AuthIntent } from "@lib/routes";

interface SocialAuthButtonsProps {
  /** Hint text — "Sign in with" or "Sign up with". */
  verb?: "Continue with" | "Sign in with" | "Sign up with";
  intent?: AuthIntent | null;
  className?: string;
}

const GoogleGlyph = () => (
  <svg viewBox="0 0 24 24" className="w-4 h-4" aria-hidden>
    <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.56c2.08-1.92 3.28-4.74 3.28-8.1Z"/>
    <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.65l-3.56-2.77c-.99.66-2.25 1.06-3.72 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84A11 11 0 0 0 12 23Z"/>
    <path fill="#FBBC05" d="M5.84 14.11A6.6 6.6 0 0 1 5.5 12c0-.73.13-1.44.34-2.11V7.05H2.18A11 11 0 0 0 1 12c0 1.78.43 3.46 1.18 4.95l3.66-2.84Z"/>
    <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1A11 11 0 0 0 2.18 7.05l3.66 2.84C6.71 7.31 9.14 5.38 12 5.38Z"/>
  </svg>
);

export default function SocialAuthButtons({
  verb = "Continue with",
  intent,
  className,
}: SocialAuthButtonsProps) {
  const handleGoogle = () => {
    if (typeof window === "undefined") return;
    const google_oauth_start = authService.startOauth(SocialProvider.GOOGLE, intent ?? undefined);
    console.log("google_oauth_start: ", google_oauth_start)
    // window.location.href = google_oauth_start
  };

  return (
    <div className={className}>
      <div className="grid grid-cols-1 gap-3">
        <button
          type="button"
          onClick={handleGoogle}
          className="group inline-flex items-center justify-center gap-2.5 px-4 py-3 rounded-lg text-sm font-semibold transition-all duration-150 hover:bg-[var(--brand-surface-low)]"
          style={{
            backgroundColor: "var(--brand-surface-card)",
            color: "var(--brand-navy)",
            border: "1px solid rgba(196,198,207,0.4)",
            boxShadow: "0 1px 2px rgba(0,13,34,0.04)",
          }}
        >
          <GoogleGlyph />
          {verb} Google
        </button>
      </div>
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
