"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Eye, EyeOff, ShieldCheck, AlertTriangle } from "lucide-react";
import { Input } from "@3rdparty/ui/input";
import { Button } from "@3rdparty/ui/button";
import AuthShell from "../AuthShell";
import AuthHeading from "../AuthHeading";
import PasswordStrengthMeter from "../PasswordStrengthMeter";
import { useResetPasswordMutation } from "../libs/useAuthQueries";
import { resetPasswordSchema, type ResetPasswordValues } from "../schemas";
import { ROUTES } from "@lib/routes";
import { useAuthStore } from "@components/website/auth/libs/useAuthStore";
import { getErrorMessage } from "@lib/utils";

interface Props {
  token: string;
}

export default function ResetPasswordContainer({ token }: Props) {
  const router = useRouter();
  const clearAuth = useAuthStore((s) => s.clear);
  const [showPassword, setShowPassword] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const resetMutation = useResetPasswordMutation();

  const form = useForm<ResetPasswordValues>({
    resolver: zodResolver(resetPasswordSchema),
    defaultValues: { password: "", confirmPassword: "" },
    mode: "onBlur",
  });

  const password = form.watch("password");

  const onSubmit = async (values: ResetPasswordValues) => {
    setErrorMessage(null);
    try {
      await resetMutation.mutateAsync({ token, password: values.password });
      // PRD §2.1: all sessions invalidated on reset — clear local mirror.
      clearAuth();
      router.push(`${ROUTES.AUTH.LOGIN}?reset=ok`);
    } catch (err) {
      setErrorMessage(
        getErrorMessage(
          err as Error,
          "This reset link is invalid or has expired. Please request a new one.",
        ),
      );
    }
  };

  return (
    <AuthShell
      panelHeading="Choose a strong new password."
      panelCopy="When you reset, every active session signs out automatically. Sign in again on your trusted devices."
    >
      <AuthHeading
        eyebrow="Reset password"
        title="Set a new password."
        subtitle="Choose something you'll remember but no one else can guess."
      />

      <div
        className="mb-6 p-4 rounded-xl flex items-start gap-3"
        style={{
          backgroundColor: "rgba(0,13,34,0.04)",
          border: "1px solid rgba(196,198,207,0.4)",
        }}
      >
        <ShieldCheck className="w-5 h-5 shrink-0 mt-0.5" style={{ color: "var(--brand-viridian)" }} />
        <p className="text-xs leading-relaxed" style={{ color: "var(--brand-on-surface-variant)" }}>
          For your safety, resetting your password signs out every other device.
        </p>
      </div>

      <form className="space-y-5" onSubmit={form.handleSubmit(onSubmit)} noValidate>
        <div className="space-y-1.5">
          <label className="text-sm font-semibold" style={{ color: "var(--brand-navy)" }}>
            New password
          </label>
          <div className="relative">
            <Input
              type={showPassword ? "text" : "password"}
              autoComplete="new-password"
              placeholder="At least 8 characters"
              className="pr-10"
              {...form.register("password")}
            />
            <button
              type="button"
              onClick={() => setShowPassword((v) => !v)}
              tabIndex={-1}
              aria-label={showPassword ? "Hide password" : "Show password"}
              className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 rounded-md transition-colors hover:bg-[var(--brand-surface-low)]"
            >
              {showPassword ? (
                <EyeOff className="w-4 h-4" style={{ color: "var(--brand-on-surface-variant)" }} />
              ) : (
                <Eye className="w-4 h-4" style={{ color: "var(--brand-on-surface-variant)" }} />
              )}
            </button>
          </div>
          <PasswordStrengthMeter password={password ?? ""} className="mt-2" />
          {form.formState.errors.password && (
            <p className="text-xs" style={{ color: "var(--danger)" }}>
              {form.formState.errors.password.message}
            </p>
          )}
        </div>

        <div className="space-y-1.5">
          <label className="text-sm font-semibold" style={{ color: "var(--brand-navy)" }}>
            Confirm new password
          </label>
          <Input
            type={showPassword ? "text" : "password"}
            autoComplete="new-password"
            placeholder="Type it again"
            {...form.register("confirmPassword")}
          />
          {form.formState.errors.confirmPassword && (
            <p className="text-xs" style={{ color: "var(--danger)" }}>
              {form.formState.errors.confirmPassword.message}
            </p>
          )}
        </div>

        {errorMessage && (
          <div
            className="p-3 rounded-lg text-sm flex items-start gap-2"
            style={{
              backgroundColor: "rgba(186,26,26,0.06)",
              color: "var(--danger)",
              border: "1px solid rgba(186,26,26,0.18)",
            }}
          >
            <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
            {errorMessage}
          </div>
        )}

        <Button
          type="submit"
          className="w-full"
          size="lg"
          disabled={resetMutation.isPending}
        >
          {resetMutation.isPending ? "Updating…" : "Reset password"}
        </Button>

        <p className="text-sm text-center" style={{ color: "var(--brand-on-surface-variant)" }}>
          <Link
            href={ROUTES.AUTH.LOGIN}
            className="font-semibold underline-offset-2 hover:underline"
            style={{ color: "var(--brand-navy)" }}
          >
            Back to sign in
          </Link>
        </p>
      </form>
    </AuthShell>
  );
}
