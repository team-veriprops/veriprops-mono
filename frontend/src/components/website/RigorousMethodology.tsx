import { methodologySteps } from "./home.data";
import { AuthIntent } from "./auth/models";
import { ROUTES, buildAuthUrl } from "@lib/routes";
import { cn } from "@lib/utils";

export default function RigorousMethodology() {
  return (
    <section
      id="how-it-works"
      className="py-24 lg:py-32 bg-white"
    >
      <div className="max-w-7xl mx-auto px-6 lg:px-8">
        {/* Centered header */}
        <div className="text-center max-w-2xl mx-auto mb-20">
          <div
            className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-widest mb-4 bg-brand-viridian/8 text-brand-viridian border border-brand-viridian/15"
          >
            Our methodology
          </div>
          <h2
            className="text-4xl md:text-5xl font-extrabold editorial-spacing font-display leading-tight mb-5 text-brand-navy"
          >
            Five steps. No shortcuts. No assumptions.
          </h2>
        </div>

        {/* Steps */}
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4 md:gap-2">
          {methodologySteps.map((step, idx) => {
            const isFirst = idx === 0;
            const isLast = idx === methodologySteps.length - 1;

            return (
              <div key={step.step} className="relative flex flex-col items-center text-center group">
                {/* Connector line (all except last) */}
                {!isLast && (
                  <div
                    className="hidden md:block absolute left-1/2 top-6 w-full h-0.5 z-0 bg-[linear-gradient(to_right,rgba(196,198,207,0.4),rgba(196,198,207,0.2))]"
                  />
                )}

                {/* Step circle */}
                <div
                  className={cn(
                    "relative z-10 w-12 h-12 rounded-full flex items-center justify-center font-bold text-sm mb-6 transition-transform duration-200 group-hover:scale-110",
                    isFirst
                      ? "signature-gradient text-white shadow-[0_4px_16px_rgba(0,13,34,0.3)]"
                      : isLast
                      ? "bg-brand-viridian/10 text-brand-viridian border-2 border-brand-viridian"
                      : "bg-brand-surface-low text-brand-navy border border-brand-outline-variant/40"
                  )}
                >
                  {step.step}
                </div>

                <h3
                  className="font-bold font-display text-sm mb-2 text-brand-navy"
                >
                  {step.title}
                </h3>
                <p className="text-sm leading-relaxed px-1 text-brand-on-surface-variant">
                  {step.description}
                </p>
              </div>
            );
          })}
        </div>

        {/* Bottom CTA strip */}
        <div
          className="mt-20 rounded-2xl p-8 flex flex-col md:flex-row items-center justify-between gap-6 bg-brand-surface-low"
        >
          <div>
            <div
              className="text-lg font-bold font-display mb-1 text-brand-navy"
            >
              Ready to verify your property?
            </div>
            <p className="text-sm text-brand-on-surface-variant">
              Get started in under 5 minutes. Your Verification ID is assigned instantly.
            </p>
          </div>
          <a
            href={buildAuthUrl(ROUTES.AUTH.GATE, { intent: AuthIntent.VERIFY })}
            className="flex-shrink-0 inline-flex items-center gap-2 signature-gradient text-white px-8 py-3.5 rounded-xl font-semibold text-sm transition-all hover:opacity-90 hover:scale-[0.98] shadow-[0_6px_20px_-4px_rgba(0,13,34,0.35)]"
          >
            Start Your Verification
          </a>
        </div>
      </div>
    </section>
  );
}
