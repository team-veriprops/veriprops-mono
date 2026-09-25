import { ReactNode } from "react";
import { LifeBuoy, type LucideIcon } from "lucide-react";
import BrandBackdrop from "@components/ui/BrandBackdrop";
import BrandLogo from "@components/ui/BrandLogo";
import { SUPPORT_EMAIL } from "@lib/config/app";

interface StatusPageProps {
  /** The HTTP status the page stands for (e.g. 404), shown in the eyebrow pill. */
  code: number;
  /** A short uppercase label naming the situation beside the code (e.g. "Restricted area"). */
  eyebrow: string;
  /** Shown in the navy seal tile above the eyebrow. */
  icon: LucideIcon;
  title: string;
  message: ReactNode;
  /** Where the visitor can go next — shared `Button asChild` links. */
  actions: ReactNode;
}

/**
 * Full-page dead end (not found, forbidden, crash): the brand, what happened, where to go next,
 * and a way to reach support. Every visitor who hits one needs a visible way out, so the actions
 * are required rather than optional. Laid out in the landing page's editorial language — seal,
 * eyebrow pill, display headline — with regions separated by tone rather than rules.
 */
export default function StatusPage({ code, eyebrow, icon: Icon, title, message, actions }: StatusPageProps) {
  return (
    <main className="relative flex min-h-dvh flex-col overflow-hidden bg-brand-surface-card">
      <BrandBackdrop glow />

      <header className="relative mx-auto w-full max-w-7xl px-4 pt-6 sm:px-6 lg:px-8 lg:pt-8">
        <BrandLogo />
      </header>

      <div className="relative mx-auto flex w-full max-w-7xl flex-1 items-center px-4 py-12 sm:px-6 lg:px-8 lg:py-20">
        <div className="w-full max-w-2xl">
          <div className="animate-fade-up motion-reduce:animate-none">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-sidebar shadow-lg ring-8 ring-brand-viridian/8">
              <Icon aria-hidden className="h-6 w-6 text-white" strokeWidth={1.75} />
            </div>

            <p className="mt-8 inline-flex items-center rounded-full border border-brand-viridian/15 bg-brand-viridian/8 px-3 py-1 text-xs font-semibold uppercase tracking-widest text-brand-viridian">
              {code} · {eyebrow}
            </p>

            <h1 className="mt-5 font-display text-4xl font-extrabold leading-[1.1] text-brand-navy editorial-spacing md:text-5xl">
              {title}
            </h1>
            <p className="mt-5 max-w-xl text-base leading-relaxed text-brand-on-surface-variant md:text-lg">
              {message}
            </p>
          </div>

          <div className="mt-10 flex flex-col gap-3 animate-fade-up stagger-1 motion-reduce:animate-none sm:flex-row">
            {actions}
          </div>

          <div className="mt-12 flex items-start gap-4 rounded-2xl bg-brand-surface-low p-5 animate-fade-up stagger-2 motion-reduce:animate-none">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-viridian/10">
              <LifeBuoy aria-hidden className="h-4.5 w-4.5 text-brand-viridian" strokeWidth={1.75} />
            </div>
            <p className="text-sm leading-relaxed text-brand-on-surface-variant">
              <span className="block font-semibold text-brand-navy">Need a hand?</span>
              Write to{" "}
              <a
                href={`mailto:${SUPPORT_EMAIL}`}
                className="break-all font-medium text-brand-viridian underline underline-offset-2"
              >
                {SUPPORT_EMAIL}
              </a>{" "}
              and we&rsquo;ll help you find your way.
            </p>
          </div>
        </div>
      </div>
    </main>
  );
}
