"use client";

import { toast } from "sonner";

import SetPasswordForm from "@components/website/auth/password/SetPasswordForm";

export default function AccountPasswordPage() {
  return (
    <div className="max-w-xl mx-auto px-4 md:px-8 py-8" data-testid="account-password">
      <header className="mb-6">
        <h1 className="text-2xl font-bold text-brand-navy">
          Password
        </h1>
        <p className="text-sm mt-1 text-brand-on-surface-variant">
          Set or change your password. A password lets you sign in even if a linked social
          provider is unavailable.
        </p>
      </header>

      <SetPasswordForm
        testIds={{
          form: "account-password-form",
          current: "account-password-current",
          input: "account-password-input",
          confirm: "account-password-confirm",
          submit: "account-password-submit",
        }}
        submitClassName="w-full"
        onSaved={() => toast.success("Password saved. Every other device has been signed out.")}
      />
    </div>
  );
}
