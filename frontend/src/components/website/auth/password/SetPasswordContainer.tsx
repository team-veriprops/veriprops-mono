"use client";

import { useRouter } from "next/navigation";
import { Button } from "@3rdparty/ui/button";
import AuthShell from "../AuthShell";
import AuthHeading from "../AuthHeading";
import SetPasswordForm from "./SetPasswordForm";
import { ROUTES } from "@lib/routes";

/** Offered after a social signup: add a password so the account can sign in without the provider. */
export default function SetPasswordContainer() {
  const router = useRouter();

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

      <SetPasswordForm
        testIds={{
          form: "set-password-form",
          current: "set-password-current-input",
          input: "set-password-input",
          confirm: "set-password-confirm-input",
          submit: "set-password-submit",
        }}
        onSaved={() => router.push(`${ROUTES.ACCOUNT.SECURITY}?password=ok`)}
        secondaryAction={
          <Button
            type="button"
            variant="outline"
            className="flex-1"
            size="lg"
            data-testid="set-password-skip"
            onClick={() => router.push(ROUTES.ACCOUNT.ROOT)}
          >
            Skip for now
          </Button>
        }
      />
    </AuthShell>
  );
}
