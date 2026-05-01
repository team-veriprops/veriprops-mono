"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Eye, EyeOff, AlertTriangle, Lock, ShieldAlert } from "lucide-react";
import { Input } from "@3rdparty/ui/input";
import { Button } from "@3rdparty/ui/button";
import { Checkbox } from "@3rdparty/ui/checkbox";
import AuthShell from "../AuthShell";
import AuthHeading from "../AuthHeading";
import SocialAuthButtons, { AuthDivider } from "../SocialAuthButtons";
import { useLoginMutation } from "../libs/useAuthQueries";
import {
  loginSchema,
  type LoginValues,
  RATE_LIMIT_LOCKOUT_AT,
  RATE_LIMIT_LOCKOUT_MINUTES,
  RATE_LIMIT_WARN_AT,
} from "../schemas";
import { ROUTES, isAuthIntent, buildAuthUrl } from "@lib/routes";
import { resolvePostAuthRedirect } from "@components/website/auth/libs/auth/redirect";
import { getDeviceFingerprint } from "@components/website/auth/libs/auth/fingerprint";
import { getErrorMessage } from "@lib/utils";

const LOCKOUT_KEY = "veriprops-login-lockout";
const ATTEMPTS_KEY = "veriprops-login-attempts";

interface LockoutState {
  count: number;
  lockedUntil?: number; // epoch ms
}

function readLockoutState(): LockoutState {
  if (typeof window === "undefined") return { count: 0 };
  try {
    const raw = localStorage.getItem(LOCKOUT_KEY);
    return raw ? (JSON.parse(raw) as LockoutState) : { count: 0 };
  } catch {
    return { count: 0 };
  }
}

function writeLockoutState(state: LockoutState) {
  try {
    localStorage.setItem(LOCKOUT_KEY, JSON.stringify(state));
    localStorage.setItem(ATTEMPTS_KEY, String(state.count));
  } catch {
    /* noop */
  }
}

export default function LoginContainer() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const intentParam = searchParams.get("intent");
  const intent = isAuthIntent(intentParam) ? intentParam : "default";
  const tier = searchParams.get("tier");
  const redirect = searchParams.get("redirect");

  const [showPassword, setShowPassword] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [lockout, setLockout] = useState<LockoutState>({ count: 0 });
  const [now, setNow] = useState(() => Date.now());
  const tickRef = useRef<NodeJS.Timeout | null>(null);

  const loginMutation = useLoginMutation();

  // Hydrate lockout from storage on mount.
  useEffect(() => {
    setLockout(readLockoutState());
  }, []);

  // Tick clock while locked, so countdown updates.
  useEffect(() => {
    if (lockout.lockedUntil && lockout.lockedUntil > Date.now()) {
      tickRef.current = setInterval(() => setNow(Date.now()), 1000);
      return () => {
        if (tickRef.current) clearInterval(tickRef.current);
      };
    }
    return;
  }, [lockout.lockedUntil]);

  const form = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "", rememberMe: false },
    mode: "onBlur",
  });

  const isLockedNow = !!lockout.lockedUntil && lockout.lockedUntil > now;
  const remainingSeconds = useMemo(
    () => (isLockedNow ? Math.ceil(((lockout.lockedUntil ?? 0) - now) / 1000) : 0),
    [isLockedNow, lockout.lockedUntil, now],
  );

  const onSubmit = async (values: LoginValues) => {
    if (isLockedNow) return;
    setErrorMessage(null);

    try {
      const res = await loginMutation.mutateAsync({
        ...values,
        deviceFingerprint: getDeviceFingerprint(),
      } as never);
      // Reset attempts on success.
      writeLockoutState({ count: 0 });
      setLockout({ count: 0 });

      const user = res.data?.user;
      const dest = user
        ? resolvePostAuthRedirect(user, { intent, redirect })
        : ROUTES.PORTAL.DASHBOARD;
      router.push(dest);
    } catch (err) {
      const next: LockoutState = { count: lockout.count + 1 };
      if (next.count >= RATE_LIMIT_LOCKOUT_AT) {
        next.lockedUntil = Date.now() + RATE_LIMIT_LOCKOUT_MINUTES * 60_000;
      }
      writeLockoutState(next);
      setLockout(next);
      setErrorMessage(
        getErrorMessage(err as Error, "Email or password is incorrect."),
      );
    }
  };

  const showWarning =
    !isLockedNow &&
    lockout.count >= RATE_LIMIT_WARN_AT &&
    lockout.count < RATE_LIMIT_LOCKOUT_AT;
  const remainingBeforeLockout = RATE_LIMIT_LOCKOUT_AT - lockout.count;

  return (
    <AuthShell panelHeading="Welcome back." panelCopy="Pick up where you left off — your verifications, evidence, and reports are exactly where you left them.">
      <AuthHeading
        eyebrow="Sign in"
        title="Sign in to Veriprops."
        subtitle="Enter your email and password to continue."
      />

      {isLockedNow && (
        <div
          className="mb-6 p-4 rounded-xl flex items-start gap-3"
          style={{
            backgroundColor: "rgba(186,26,26,0.06)",
            border: "1px solid rgba(186,26,26,0.18)",
            color: "var(--danger)",
          }}
        >
          <ShieldAlert className="w-5 h-5 shrink-0 mt-0.5" />
          <div className="text-sm leading-relaxed">
            <strong className="block">Account temporarily locked.</strong>
            Too many failed attempts. Try again in{" "}
            <span className="font-mono font-semibold">
              {Math.floor(remainingSeconds / 60)}:{String(remainingSeconds % 60).padStart(2, "0")}
            </span>
            , or use{" "}
            <Link
              href={ROUTES.AUTH.FORGOT_PASSWORD}
              className="underline font-semibold"
              style={{ color: "var(--danger)" }}
            >
              Forgot password
            </Link>{" "}
            to reset.
          </div>
        </div>
      )}

      {showWarning && (
        <div
          className="mb-6 p-4 rounded-xl flex items-start gap-3"
          style={{
            backgroundColor: "rgba(176,125,0,0.06)",
            border: "1px solid rgba(176,125,0,0.2)",
            color: "var(--warning)",
          }}
        >
          <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
          <p className="text-sm leading-relaxed">
            <strong>{remainingBeforeLockout} attempts remaining.</strong> After {RATE_LIMIT_LOCKOUT_AT} failed attempts you&apos;ll be locked out for {RATE_LIMIT_LOCKOUT_MINUTES} minutes.
          </p>
        </div>
      )}

      <form className="space-y-5" onSubmit={form.handleSubmit(onSubmit)} noValidate>
        <div className="space-y-1.5">
          <label className="text-sm font-semibold" style={{ color: "var(--brand-navy)" }}>
            Email
          </label>
          <Input
            type="email"
            autoComplete="email"
            placeholder="you@example.com"
            disabled={isLockedNow}
            {...form.register("email")}
          />
          {form.formState.errors.email && (
            <p className="text-xs" style={{ color: "var(--danger)" }}>
              {form.formState.errors.email.message}
            </p>
          )}
        </div>

        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <label className="text-sm font-semibold" style={{ color: "var(--brand-navy)" }}>
              Password
            </label>
            <Link
              href={buildAuthUrl(ROUTES.AUTH.FORGOT_PASSWORD, { redirect })}
              className="text-xs font-semibold"
              style={{ color: "var(--brand-viridian)" }}
            >
              Forgot password?
            </Link>
          </div>
          <div className="relative">
            <Input
              type={showPassword ? "text" : "password"}
              autoComplete="current-password"
              placeholder="Your password"
              disabled={isLockedNow}
              className="pr-10"
              {...form.register("password")}
            />
            <button
              type="button"
              aria-label={showPassword ? "Hide password" : "Show password"}
              className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 rounded-md transition-colors hover:bg-[var(--brand-surface-low)]"
              onClick={() => setShowPassword((v) => !v)}
              tabIndex={-1}
            >
              {showPassword ? (
                <EyeOff className="w-4 h-4" style={{ color: "var(--brand-on-surface-variant)" }} />
              ) : (
                <Eye className="w-4 h-4" style={{ color: "var(--brand-on-surface-variant)" }} />
              )}
            </button>
          </div>
          {form.formState.errors.password && (
            <p className="text-xs" style={{ color: "var(--danger)" }}>
              {form.formState.errors.password.message}
            </p>
          )}
        </div>

        <label className="flex items-center gap-2.5 cursor-pointer select-none">
          <Checkbox
            checked={form.watch("rememberMe")}
            onCheckedChange={(v) => form.setValue("rememberMe", v === true)}
          />
          <span className="text-sm" style={{ color: "var(--brand-on-surface)" }}>
            Keep me signed in for 30 days
          </span>
        </label>

        {errorMessage && !isLockedNow && (
          <div
            className="p-3 rounded-lg text-sm flex items-start gap-2"
            style={{
              backgroundColor: "rgba(186,26,26,0.06)",
              color: "var(--danger)",
              border: "1px solid rgba(186,26,26,0.18)",
            }}
          >
            <Lock className="w-4 h-4 shrink-0 mt-0.5" />
            {errorMessage}
          </div>
        )}

        <Button
          type="submit"
          className="w-full"
          size="lg"
          disabled={isLockedNow || loginMutation.isPending}
        >
          {loginMutation.isPending ? "Signing in…" : "Sign in"}
        </Button>
      </form>

      <AuthDivider />
      <SocialAuthButtons verb="Sign in with" intent={intent} />

      <p className="mt-8 text-sm text-center" style={{ color: "var(--brand-on-surface-variant)" }}>
        New to Veriprops?{" "}
        <Link
          href={buildAuthUrl(ROUTES.AUTH.SIGNUP, { intent, tier, redirect })}
          className="font-semibold underline-offset-2 hover:underline"
          style={{ color: "var(--brand-navy)" }}
        >
          Create an account
        </Link>
      </p>
    </AuthShell>
  );
}
