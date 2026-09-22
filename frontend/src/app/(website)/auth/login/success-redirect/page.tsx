
import Link from "next/link";
import { CheckCircle } from "lucide-react";
import { ROUTES } from "@/lib/routes";

export default function LoginSuccessPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-brand-surface px-6 py-12">
      <div className="w-full max-w-md rounded-3xl border border-brand-outline-variant bg-brand-surface-card p-10 shadow-xl">
        <div className="flex flex-col items-center text-center">
          <div className="mb-6 rounded-full bg-brand-viridian/10 p-4">
            <CheckCircle className="h-14 w-14 text-brand-viridian" />
          </div>

          <h1 className="text-3xl font-bold tracking-tight text-brand-on-surface">
            Login Successful
          </h1>

          <p className="mt-3 text-sm leading-6 text-brand-on-surface-variant">
            Welcome back! Your account has been authenticated successfully.
          </p>

          <div className="mt-8 w-full space-y-3">

            <Link
              href={ROUTES.ADMIN.DASHBOARD}
              className="flex h-12 w-full items-center justify-center rounded-xl border border-brand-outline-variant bg-brand-surface-card text-sm font-medium text-brand-on-surface transition hover:bg-brand-surface-low"
            >
              Continue to Dashboard
            </Link>
          </div>
        </div>
      </div>
    </main>
  );
}
