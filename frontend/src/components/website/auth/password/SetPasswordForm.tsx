"use client";

import { ReactNode, useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { AlertTriangle, Eye, EyeOff, Loader2 } from "lucide-react";

import { Input } from "@3rdparty/ui/input";
import { SubmitButton } from "@components/ui/form/SubmitButton";
import PasswordStrengthMeter from "../PasswordStrengthMeter";
import { useCurrentSession, useSetPasswordMutation } from "../libs/useAuthQueries";
import { setPasswordSchema, type SetPasswordValues } from "../schemas";
import { getErrorMessage } from "@lib/errors";

/** Stable automation selectors; each surface keeps the ones its specs already use. */
export interface SetPasswordTestIds {
  form: string;
  current: string;
  input: string;
  confirm: string;
  submit: string;
}

interface Props {
  testIds: SetPasswordTestIds;
  /** Called once the password is saved (the session and device list are already refreshed). */
  onSaved: () => void;
  /** Rendered beside the submit button — e.g. "Skip for now". */
  secondaryAction?: ReactNode;
  submitClassName?: string;
}

/**
 * Set a first password, or change the current one, from a signed-in session (§1.3).
 *
 * Whether the account already has a password comes from the session: when it does, the
 * current password is asked for, because the backend refuses a change without it. Saving
 * signs out every other device and keeps this one.
 */
export default function SetPasswordForm(props: Props) {
  const session = useCurrentSession();
  if (session.isLoading || !session.data) {
    return (
      <div className="flex justify-center py-8">
        <Loader2 className="w-5 h-5 animate-spin text-brand-on-surface-variant" aria-label="Loading" />
      </div>
    );
  }
  const hasPassword = session.data.user.hasPassword;
  // Keyed on hasPassword: the resolver's schema depends on it, and it flips after a first save.
  return <PasswordFields key={String(hasPassword)} hasPassword={hasPassword} {...props} />;
}

function PasswordFields({
  hasPassword, testIds, onSaved, secondaryAction, submitClassName,
}: Props & { hasPassword: boolean }) {
  const [showPassword, setShowPassword] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const setPassword = useSetPasswordMutation();

  const form = useForm<SetPasswordValues>({
    resolver: zodResolver(setPasswordSchema(hasPassword)),
    defaultValues: { currentPassword: "", password: "", confirmPassword: "" },
    mode: "onBlur",
  });
  const password = useWatch({ control: form.control, name: "password" });
  const inputType = showPassword ? "text" : "password";
  const { errors } = form.formState;

  const onSubmit = async (values: SetPasswordValues) => {
    setErrorMessage(null);
    try {
      await setPassword.mutateAsync({
        password: values.password,
        currentPassword: hasPassword ? values.currentPassword : undefined,
      });
      form.reset();
      onSaved();
    } catch (err) {
      setErrorMessage(getErrorMessage(err, "Could not save your password. Please try again."));
    }
  };

  return (
    // method="post" so that a submit landing before hydration cannot put a password in the
    // URL — see SubmitButton.
    <form
      className="space-y-5"
      method="post"
      onSubmit={form.handleSubmit(onSubmit)}
      noValidate
      data-testid={testIds.form}
    >
      {hasPassword && (
        <div className="space-y-1.5">
          <label htmlFor={testIds.current} className="text-sm font-semibold text-brand-navy">
            Current password
          </label>
          <Input
            id={testIds.current}
            type={inputType}
            autoComplete="current-password"
            data-testid={testIds.current}
            {...form.register("currentPassword")}
          />
          {errors.currentPassword && (
            <p className="text-xs text-danger">{errors.currentPassword.message}</p>
          )}
        </div>
      )}

      <div className="space-y-1.5">
        <label htmlFor={testIds.input} className="text-sm font-semibold text-brand-navy">
          New password
        </label>
        <div className="relative">
          <Input
            id={testIds.input}
            type={inputType}
            autoComplete="new-password"
            placeholder="At least 8 characters"
            className="pr-10"
            data-testid={testIds.input}
            {...form.register("password")}
          />
          <button
            type="button"
            onClick={() => setShowPassword((v) => !v)}
            tabIndex={-1}
            aria-label={showPassword ? "Hide password" : "Show password"}
            className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 rounded-md transition-colors hover:bg-brand-surface-low"
          >
            {showPassword ? (
              <EyeOff className="w-4 h-4 text-brand-on-surface-variant" />
            ) : (
              <Eye className="w-4 h-4 text-brand-on-surface-variant" />
            )}
          </button>
        </div>
        <PasswordStrengthMeter password={password ?? ""} className="mt-2" />
        {errors.password && <p className="text-xs text-danger">{errors.password.message}</p>}
      </div>

      <div className="space-y-1.5">
        <label htmlFor={testIds.confirm} className="text-sm font-semibold text-brand-navy">
          Confirm new password
        </label>
        <Input
          id={testIds.confirm}
          type={inputType}
          autoComplete="new-password"
          placeholder="Type it again"
          data-testid={testIds.confirm}
          {...form.register("confirmPassword")}
        />
        {errors.confirmPassword && (
          <p className="text-xs text-danger">{errors.confirmPassword.message}</p>
        )}
      </div>

      {hasPassword && (
        <p className="text-xs text-brand-on-surface-variant">
          Saving signs you out on every other device.
        </p>
      )}

      {errorMessage && (
        <div role="alert" className="p-3 rounded-lg text-sm flex items-start gap-2 bg-danger/6 text-danger border border-danger/18">
          <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
          {errorMessage}
        </div>
      )}

      <div className="flex gap-3">
        {secondaryAction}
        <SubmitButton
          className={submitClassName ?? "flex-1"}
          size="lg"
          data-testid={testIds.submit}
          disabled={setPassword.isPending}
        >
          {setPassword.isPending ? "Saving…" : "Save password"}
        </SubmitButton>
      </div>
    </form>
  );
}
