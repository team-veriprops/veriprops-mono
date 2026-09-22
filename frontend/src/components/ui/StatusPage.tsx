import { ReactNode } from "react";
import BrandLogo from "@components/ui/BrandLogo";
import { SUPPORT_EMAIL } from "@lib/config/app";

interface StatusPageProps {
  /** The HTTP status the page stands for, shown as the page's eyebrow (e.g. 404). */
  code: number;
  title: string;
  message: ReactNode;
  /** Where the visitor can go next — shared `Button asChild` links. */
  actions: ReactNode;
}

/**
 * Full-page dead end (not found, forbidden): the brand, what happened, where to go next, and a
 * way to reach support. Every visitor who hits one needs a visible way out, so the actions are
 * required rather than optional.
 */
export default function StatusPage({ code, title, message, actions }: StatusPageProps) {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-brand-surface px-4 py-12">
      <div className="w-full max-w-lg rounded-2xl border border-brand-outline-variant bg-brand-surface-card p-6 shadow-card sm:p-10">
        <BrandLogo size="sm" />

        <p className="mt-8 font-mono text-sm font-semibold text-brand-viridian">{code}</p>
        <h1 className="mt-2 text-2xl font-bold tracking-tight text-brand-on-surface sm:text-3xl">{title}</h1>
        <p className="mt-3 text-base leading-7 text-brand-on-surface-variant">{message}</p>

        <div className="mt-8 flex flex-col gap-3 sm:flex-row">{actions}</div>

        <p className="mt-8 border-t border-brand-outline-variant pt-6 text-sm text-brand-on-surface-variant">
          Need help? Contact{" "}
          <a href={`mailto:${SUPPORT_EMAIL}`} className="font-medium text-brand-viridian underline underline-offset-2">
            {SUPPORT_EMAIL}
          </a>
        </p>
      </div>
    </main>
  );
}
