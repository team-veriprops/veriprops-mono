"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Eye, EyeOff } from "lucide-react";
import { toast } from "sonner";

import { Input } from "@3rdparty/ui/input";
import { Button } from "@3rdparty/ui/button";
import PasswordStrengthMeter from "@components/website/auth/PasswordStrengthMeter";
import { useSetPasswordMutation } from "@components/website/auth/libs/useAuthQueries";
import { resetPasswordSchema, type ResetPasswordValues } from "@components/website/auth/schemas";
import { getErrorMessage } from "@lib/utils";

export default function AccountPasswordPage() {
  const [showPassword, setShowPassword] = useState(false);
  const setPassword = useSetPasswordMutation();
  const form = useForm<ResetPasswordValues>({
    resolver: zodResolver(resetPasswordSchema),
    defaultValues: { password: "", confirmPassword: "" },
    mode: "onBlur",
  });
  const password = form.watch("password");

  const onSubmit = async (values: ResetPasswordValues) => {
    try {
      await setPassword.mutateAsync({ password: values.password });
      form.reset();
      toast.success("Password updated.");
    } catch (err) {
      toast.error(getErrorMessage(err as Error, "Could not set your password. Please try again."));
    }
  };

  return (
    <div className="max-w-xl mx-auto px-4 md:px-8 py-8" data-testid="account-password">
      <header className="mb-6">
        <h1 className="text-2xl font-bold" style={{ color: "var(--brand-navy)" }}>
          Password
        </h1>
        <p className="text-sm mt-1" style={{ color: "var(--brand-on-surface-variant)" }}>
          Set or change your password. A password lets you sign in even if a linked social
          provider is unavailable.
        </p>
      </header>

      <form
        className="space-y-5"
        onSubmit={form.handleSubmit(onSubmit)}
        noValidate
        data-testid="account-password-form"
      >
        <div className="space-y-1.5">
          <label className="text-sm font-semibold" style={{ color: "var(--brand-navy)" }}>
            New password
          </label>
          <div className="relative">
            <Input
              type={showPassword ? "text" : "password"}
              autoComplete="new-password"
              data-testid="account-password-input"
              {...form.register("password")}
            />
            <button
              type="button"
              onClick={() => setShowPassword((s) => !s)}
              aria-label={showPassword ? "Hide password" : "Show password"}
              className="absolute right-3 top-1/2 -translate-y-1/2"
              style={{ color: "var(--brand-on-surface-variant)" }}
            >
              {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
          {form.formState.errors.password && (
            <p className="text-xs" style={{ color: "var(--brand-destructive, #ba1a1a)" }}>
              {form.formState.errors.password.message}
            </p>
          )}
          <PasswordStrengthMeter password={password} />
        </div>

        <div className="space-y-1.5">
          <label className="text-sm font-semibold" style={{ color: "var(--brand-navy)" }}>
            Confirm password
          </label>
          <Input
            type={showPassword ? "text" : "password"}
            autoComplete="new-password"
            data-testid="account-password-confirm"
            {...form.register("confirmPassword")}
          />
          {form.formState.errors.confirmPassword && (
            <p className="text-xs" style={{ color: "var(--brand-destructive, #ba1a1a)" }}>
              {form.formState.errors.confirmPassword.message}
            </p>
          )}
        </div>

        <Button
          type="submit"
          disabled={setPassword.isPending}
          data-testid="account-password-submit"
          className="w-full"
        >
          {setPassword.isPending ? "Saving…" : "Save password"}
        </Button>
      </form>
    </div>
  );
}
