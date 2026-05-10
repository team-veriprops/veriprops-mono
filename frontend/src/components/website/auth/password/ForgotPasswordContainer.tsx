"use client";

import { useState } from "react";
import Link from "next/link";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { CheckCircle2, Mail } from "lucide-react";
import { Input } from "@3rdparty/ui/input";
import { Button } from "@3rdparty/ui/button";
import AuthShell from "../AuthShell";
import AuthHeading from "../AuthHeading";
import { useForgotPasswordMutation } from "../libs/useAuthQueries";
import { forgotPasswordSchema, type ForgotPasswordValues } from "../schemas";
import { ROUTES } from "@lib/routes";

export default function ForgotPasswordContainer() {
  const [submittedEmail, setSubmittedEmail] = useState<string | null>(null);
  const forgotMutation = useForgotPasswordMutation();

  const form = useForm<ForgotPasswordValues>({
    resolver: zodResolver(forgotPasswordSchema),
    defaultValues: { email: "" },
    mode: "onBlur",
  });

  const onSubmit = async (values: ForgotPasswordValues) => {
    try {
      await forgotMutation.mutateAsync(values);
    } catch {
      /* deliberately silent — never disclose whether email exists */
    } finally {
      // Always show the same confirmation, regardless of whether the email exists.
      setSubmittedEmail(values.email);
    }
  };

  return (
    <AuthShell
      panelHeading="A reset link is on its way."
      panelCopy="Check your inbox — the link expires in 60 minutes for your security."
    >
      <AuthHeading
        eyebrow="Reset password"
        title="Forgot your password?"
        subtitle={
          submittedEmail
            ? "We've sent reset instructions if an account exists for that email."
            : "Enter the email associated with your Veriprops account and we'll send you a one-time reset link."
        }
      />

      {submittedEmail ? (
        <div className="space-y-6">
          <div
            className="p-5 rounded-xl flex items-start gap-3"
            style={{
              backgroundColor: "rgba(63,102,83,0.06)",
              border: "1px solid rgba(63,102,83,0.2)",
            }}
          >
            <CheckCircle2 className="w-5 h-5 shrink-0 mt-0.5" style={{ color: "var(--brand-viridian)" }} />
            <div>
              <p className="text-sm font-semibold" style={{ color: "var(--brand-navy)" }}>
                Check {submittedEmail}
              </p>
              <p className="text-sm mt-1 leading-relaxed" style={{ color: "var(--brand-on-surface-variant)" }}>
                If an account exists for that address, you&apos;ll receive a reset link within a few minutes. The link expires in 60 minutes.
              </p>
            </div>
          </div>

          <div className="flex gap-3">
            <Button
              type="button"
              variant="outline"
              className="flex-1"
              size="lg"
              onClick={() => setSubmittedEmail(null)}
            >
              Try another email
            </Button>
            <Link href={ROUTES.AUTH.LOGIN} className="flex-1">
              <Button type="button" className="w-full" size="lg">
                Back to sign in
              </Button>
            </Link>
          </div>
        </div>
      ) : (
        <form className="space-y-5" onSubmit={form.handleSubmit(onSubmit)} noValidate data-testid="forgot-form">
          <div className="space-y-1.5">
            <label className="text-sm font-semibold" style={{ color: "var(--brand-navy)" }}>
              Email
            </label>
            <div className="relative">
              <Mail
                className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 pointer-events-none"
                style={{ color: "var(--brand-on-surface-variant)" }}
              />
              <Input
                type="email"
                autoComplete="email"
                placeholder="you@example.com"
                className="pl-9"
                data-testid="forgot-email"
                {...form.register("email")}
              />
            </div>
            {form.formState.errors.email && (
              <p className="text-xs" style={{ color: "var(--danger)" }}>
                {form.formState.errors.email.message}
              </p>
            )}
          </div>

          <Button
            type="submit"
            className="w-full"
            size="lg"
            disabled={forgotMutation.isPending}
            data-testid="forgot-submit"
          >
            {forgotMutation.isPending ? "Sending…" : "Send reset link"}
          </Button>

          <p className="text-sm text-center" style={{ color: "var(--brand-on-surface-variant)" }}>
            Remembered it?{" "}
            <Link
              href={ROUTES.AUTH.LOGIN}
              className="font-semibold underline-offset-2 hover:underline"
              style={{ color: "var(--brand-navy)" }}
            >
              Back to sign in
            </Link>
          </p>
        </form>
      )}
    </AuthShell>
  );
}
