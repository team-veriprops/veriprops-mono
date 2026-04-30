"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Eye, EyeOff, AlertTriangle } from "lucide-react";
import { Input } from "@3rdparty/ui/input";
import { Button } from "@3rdparty/ui/button";
import AuthShell from "../AuthShell";
import AuthHeading from "../AuthHeading";
import PasswordStrengthMeter from "../PasswordStrengthMeter";
import { useSetPasswordMutation } from "../libs/useAuthQueries";
import { resetPasswordSchema, type ResetPasswordValues } from "../schemas";
import { ROUTES } from "@lib/routes";
import { getErrorMessage } from "@lib/utils";

export default function SetPasswordContainer() {
  const router = useRouter();
  const [showPassword, setShowPassword] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const setPasswordMutation = useSetPasswordMutation();

  const form = useForm<ResetPasswordValues>({
    resolver: zodResolver(resetPasswordSchema),
    defaultValues: { password: "", confirmPassword: "" },
    mode: "onBlur",
  });

  const password = form.watch("password");

  const onSubmit = async (values: ResetPasswordValues) => {
    setErrorMessage(null);
    try {
      await setPasswordMutation.mutateAsync({ password: values.password });
      router.push(`${ROUTES.ACCOUNT.SECURITY}?password=ok`);
    } catch (err) {
      setErrorMessage(
        getErrorMessage(err as Error, "Could not set your password. Please try again."),
      );
    }
  };

  return (
    <AuthShell
      panelHeading="Add a password to your account."
      panelCopy="A password lets you sign in even if your social provider is unavailable. You'll keep your linked accounts."
    >
      <AuthHeading
        eyebrow="Account security"
        title="Set a password."
        subtitle="You signed up with a social account. Adding a password is optional but recommended."
      />

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

        <div className="flex gap-3">
          <Button
            type="button"
            variant="outline"
            className="flex-1"
            size="lg"
            onClick={() => router.push(ROUTES.ACCOUNT.ROOT)}
          >
            Skip for now
          </Button>
          <Button
            type="submit"
            className="flex-1"
            size="lg"
            disabled={setPasswordMutation.isPending}
          >
            {setPasswordMutation.isPending ? "Saving…" : "Save password"}
          </Button>
        </div>
      </form>
    </AuthShell>
  );
}
