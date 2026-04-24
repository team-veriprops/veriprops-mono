import type { ComponentType, CSSProperties } from "react";
import { Upload, Search, Shield, Lock, Award } from "lucide-react";
import { methodologySteps } from "./home.data";

const iconMap: Record<string, ComponentType<{ className?: string; strokeWidth?: number; style?: CSSProperties }>> = {
  Upload,
  Search,
  Shield,
  Lock,
  Award,
};

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
            className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-widest mb-4"
            style={{
              backgroundColor: "rgba(63,102,83,0.08)",
              color: "var(--brand-viridian)",
              border: "1px solid rgba(63,102,83,0.15)",
            }}
          >
            Our Process
          </div>
          <h2
            className="text-4xl md:text-5xl font-extrabold editorial-spacing font-display leading-tight mb-5"
            style={{ color: "var(--brand-navy)" }}
          >
            A Rigorous Methodology
          </h2>
          <p className="text-lg leading-relaxed" style={{ color: "var(--brand-on-surface-variant)" }}>
            Our 5-step sovereign verification process ensures absolute certainty
            for your offshore investment — no shortcuts, no assumptions.
          </p>
        </div>

        {/* Steps */}
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4 md:gap-2">
          {methodologySteps.map((step, idx) => {
            const Icon = iconMap[step.icon] ?? Award;
            const isFirst = idx === 0;
            const isLast = idx === methodologySteps.length - 1;

            return (
              <div key={step.step} className="relative flex flex-col items-center text-center group">
                {/* Connector line (all except last) */}
                {!isLast && (
                  <div
                    className="hidden md:block absolute top-6 w-full h-[2px] z-0"
                    style={{
                      left: "50%",
                      background: "linear-gradient(to right, rgba(196,198,207,0.4), rgba(196,198,207,0.2))",
                    }}
                  />
                )}

                {/* Step circle */}
                <div
                  className="relative z-10 w-12 h-12 rounded-full flex items-center justify-center font-bold text-sm mb-6 transition-transform duration-200 group-hover:scale-110"
                  style={
                    isFirst
                      ? {
                          background: "linear-gradient(135deg, var(--brand-navy) 0%, var(--brand-navy-deep) 100%)",
                          color: "#fff",
                          boxShadow: "0 4px 16px rgba(0,13,34,0.3)",
                        }
                      : isLast
                      ? {
                          background: "rgba(63,102,83,0.1)",
                          color: "var(--brand-viridian)",
                          border: "2px solid var(--brand-viridian)",
                        }
                      : {
                          background: "var(--brand-surface-low)",
                          color: "var(--brand-navy)",
                          border: "1px solid rgba(196,198,207,0.4)",
                        }
                  }
                >
                  {step.step}
                </div>

                {/* Icon */}
                <div
                  className="w-10 h-10 rounded-xl flex items-center justify-center mb-4"
                  style={{
                    backgroundColor: isFirst
                      ? "rgba(0,13,34,0.05)"
                      : isLast
                      ? "rgba(63,102,83,0.08)"
                      : "var(--brand-surface-low)",
                  }}
                >
                  <Icon
                    className="w-5 h-5"
                    strokeWidth={1.5}
                    style={{
                      color: isFirst
                        ? "var(--brand-navy)"
                        : isLast
                        ? "var(--brand-viridian)"
                        : "var(--brand-on-surface-variant)",
                    }}
                  />
                </div>

                <h4
                  className="font-bold font-display text-sm mb-2"
                  style={{ color: "var(--brand-navy)" }}
                >
                  {step.title}
                </h4>
                <p className="text-xs leading-relaxed px-1" style={{ color: "var(--brand-on-surface-variant)" }}>
                  {step.description}
                </p>
              </div>
            );
          })}
        </div>

        {/* Bottom CTA strip */}
        <div
          className="mt-20 rounded-2xl p-8 flex flex-col md:flex-row items-center justify-between gap-6"
          style={{ backgroundColor: "var(--brand-surface-low)" }}
        >
          <div>
            <div
              className="text-lg font-bold font-display mb-1"
              style={{ color: "var(--brand-navy)" }}
            >
              Ready to verify your property?
            </div>
            <p className="text-sm" style={{ color: "var(--brand-on-surface-variant)" }}>
              Get started in under 5 minutes. Your Verification ID is assigned instantly.
            </p>
          </div>
          <a
            href="/auth?intent=verify"
            className="flex-shrink-0 inline-flex items-center gap-2 signature-gradient text-white px-8 py-3.5 rounded-xl font-semibold text-sm transition-all hover:opacity-90 hover:scale-[0.98]"
            style={{ boxShadow: "0 6px 20px -4px rgba(0,13,34,0.35)" }}
          >
            Start Your Verification
          </a>
        </div>
      </div>
    </section>
  );
}
