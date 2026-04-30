"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Eye, EyeOff } from "lucide-react";
import { Input } from "@3rdparty/ui/input";
import { Button } from "@3rdparty/ui/button";
import PasswordStrengthMeter from "../PasswordStrengthMeter";
import { signupStep1Schema, type SignupStep1Values } from "../schemas";

interface Props {
  defaultValues?: Partial<SignupStep1Values>;
  onSubmit: (values: SignupStep1Values) => void;
}

export default function AccountBasicsStep({ defaultValues, onSubmit }: Props) {
  const [showPassword, setShowPassword] = useState(false);
  const form = useForm<SignupStep1Values>({
    resolver: zodResolver(signupStep1Schema),
    defaultValues: {
      firstName: "",
      lastName: "",
      email: "",
      password: "",
      ...defaultValues,
    },
    mode: "onBlur",
  });

  const password = form.watch("password");

  return (
    <form className="space-y-5" onSubmit={form.handleSubmit(onSubmit)} noValidate>
      <div className="grid sm:grid-cols-2 gap-4">
        <Field label="First name" error={form.formState.errors.firstName?.message}>
          <Input
            autoComplete="given-name"
            placeholder="Adaeze"
            {...form.register("firstName")}
          />
        </Field>
        <Field label="Last name" error={form.formState.errors.lastName?.message}>
          <Input
            autoComplete="family-name"
            placeholder="Williams"
            {...form.register("lastName")}
          />
        </Field>
      </div>

      <Field label="Email address" error={form.formState.errors.email?.message}>
        <Input
          type="email"
          autoComplete="email"
          placeholder="you@example.com"
          {...form.register("email")}
        />
      </Field>

      <Field label="Password" error={form.formState.errors.password?.message}>
        <div className="relative">
          <Input
            type={showPassword ? "text" : "password"}
            autoComplete="new-password"
            placeholder="Create a strong password"
            {...form.register("password")}
            className="pr-10"
          />
          <button
            type="button"
            aria-label={showPassword ? "Hide password" : "Show password"}
            className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 rounded-md transition-colors hover:bg-[var(--brand-surface-low)]"
            onClick={() => setShowPassword((v) => !v)}
          >
            {showPassword ? (
              <EyeOff className="w-4 h-4" style={{ color: "var(--brand-on-surface-variant)" }} />
            ) : (
              <Eye className="w-4 h-4" style={{ color: "var(--brand-on-surface-variant)" }} />
            )}
          </button>
        </div>
        <PasswordStrengthMeter password={password ?? ""} className="mt-2" />
      </Field>

      <Button type="submit" className="w-full" size="lg">
        Continue
      </Button>
    </form>
  );
}

function Field({
  label,
  children,
  error,
}: {
  label: string;
  children: React.ReactNode;
  error?: string;
}) {
  return (
    <div className="space-y-1.5">
      <label className="text-sm font-semibold" style={{ color: "var(--brand-navy)" }}>
        {label}
      </label>
      {children}
      {error && (
        <p className="text-xs" style={{ color: "var(--danger)" }}>
          {error}
        </p>
      )}
    </div>
  );
}
