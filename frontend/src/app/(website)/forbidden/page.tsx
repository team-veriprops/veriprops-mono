import Link from "next/link";
import { ShieldAlert, ArrowLeft, LockKeyhole } from "lucide-react";
import { ROUTES } from "@/lib/routes";

export default function ForbiddenPage() {
  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-neutral-950 px-6 py-12 text-white">
      {/* Background Glow */}
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(59,130,246,0.18),transparent_45%)]" />
      <div className="absolute bottom-0 left-0 right-0 h-64 bg-[radial-gradient(circle_at_bottom,rgba(168,85,247,0.15),transparent_50%)]" />

      {/* Card */}
      <section className="relative z-10 w-full max-w-2xl rounded-3xl border border-white/10 bg-white/5 p-8 shadow-2xl backdrop-blur-xl md:p-12">
        {/* Brand */}
        <div className="mb-10 flex items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-600 shadow-lg shadow-blue-500/30">
            <LockKeyhole className="h-6 w-6" />
          </div>

          <div>
            <h2 className="text-xl font-bold tracking-tight">
              NovaStack
            </h2>
            <p className="text-sm text-neutral-400">
              Secure Workspace Platform
            </p>
          </div>
        </div>

        {/* Content */}
        <div className="space-y-6">
          <div className="inline-flex items-center gap-2 rounded-full border border-red-500/20 bg-red-500/10 px-4 py-2 text-sm font-medium text-red-300">
            <ShieldAlert className="h-4 w-4" />
            Access Restricted
          </div>

          <div>
            <h1 className="text-5xl font-black tracking-tight md:text-6xl">
              403
            </h1>

            <h2 className="mt-3 text-2xl font-semibold tracking-tight md:text-3xl">
              You don&apos;t have permission to access this page.
            </h2>

            <p className="mt-4 max-w-xl text-base leading-7 text-neutral-400">
              The page you&apos;re trying to view requires additional
              permissions or administrator approval. If you believe this is a
              mistake, contact your workspace administrator.
            </p>
          </div>

          {/* Actions */}
          <div className="flex flex-col gap-4 pt-4 sm:flex-row">
            <Link
              href={ROUTES.ADMIN.DASHBOARD}
              className="inline-flex items-center justify-center rounded-xl bg-blue-600 px-5 py-3 text-sm font-semibold text-white transition hover:bg-blue-500"
            >
              Go to Dashboard
            </Link>

            <Link
              href={ROUTES.HOME}
              className="inline-flex items-center justify-center gap-2 rounded-xl border border-white/10 bg-white/5 px-5 py-3 text-sm font-semibold text-white transition hover:bg-white/10"
            >
              <ArrowLeft className="h-4 w-4" />
              Back Home
            </Link>
          </div>
        </div>

        {/* Footer */}
        <div className="mt-10 border-t border-white/10 pt-6 text-sm text-neutral-500">
          Need help? Contact{" "}
          <a
            href="mailto:support@novastack.io"
            className="font-medium text-blue-400 hover:text-blue-300"
          >
            support@novastack.io
          </a>
        </div>
      </section>
    </main>
  );
}
