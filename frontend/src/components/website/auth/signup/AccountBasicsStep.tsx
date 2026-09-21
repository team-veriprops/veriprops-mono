"use client";

import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Eye, EyeOff } from "lucide-react";
import { Input } from "@3rdparty/ui/input";
import { SubmitButton } from "@components/ui/form/SubmitButton";
import PasswordStrengthMeter from "../PasswordStrengthMeter";
import { Field } from "@components/ui/form/Field";
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

  const password = useWatch({ control: form.control, name: "password" });

  return (
    <form
      className="space-y-5"
      method="post"
      onSubmit={form.handleSubmit(onSubmit)}
      noValidate
      data-testid="signup-basics-form"
    >
      {/* method="post" so that a submit landing before hydration cannot put the chosen
          password in the URL — see SubmitButton. */}
      <div className="grid sm:grid-cols-2 gap-4">
        <Field label="First name" error={form.formState.errors.firstName?.message}>
          {(id) => (
            <Input
              id={id}
              autoComplete="given-name"
              placeholder="Adaeze"
              data-testid="signup-first-name"
              {...form.register("firstName")}
            />
          )}
        </Field>
        <Field label="Last name" error={form.formState.errors.lastName?.message}>
          {(id) => (
            <Input
              id={id}
              autoComplete="family-name"
              placeholder="Williams"
              data-testid="signup-last-name"
              {...form.register("lastName")}
            />
          )}
        </Field>
      </div>

      <Field label="Email address" error={form.formState.errors.email?.message}>
        {(id) => (
          <Input
            id={id}
            type="email"
            autoComplete="email"
            placeholder="you@example.com"
            data-testid="signup-email"
            {...form.register("email")}
          />
        )}
      </Field>

      <Field label="Password" error={form.formState.errors.password?.message}>
        {(id) => (
          <>
        <div className="relative">
          <Input
            id={id}
            type={showPassword ? "text" : "password"}
            autoComplete="new-password"
            placeholder="Create a strong password"
            data-testid="signup-password"
            {...form.register("password")}
            className="pr-10"
          />
          <button
            type="button"
            aria-label={showPassword ? "Hide password" : "Show password"}
            className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 rounded-md transition-colors hover:bg-brand-surface-low"
            onClick={() => setShowPassword((v) => !v)}
          >
            {showPassword ? (
              <EyeOff className="w-4 h-4 text-brand-on-surface-variant" />
            ) : (
              <Eye className="w-4 h-4 text-brand-on-surface-variant" />
            )}
          </button>
        </div>
        <PasswordStrengthMeter password={password ?? ""} className="mt-2" />
          </>
        )}
      </Field>

      <SubmitButton className="w-full" size="lg" data-testid="signup-basics-submit">
        Continue
      </SubmitButton>
    </form>
  );
}
