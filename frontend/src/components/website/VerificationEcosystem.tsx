import type { ComponentType, CSSProperties } from "react";
import { BarChart3, Fingerprint, ShieldCheck } from "lucide-react";
import { ecosystemFeatures } from "./home.data";

const iconMap: Record<string, ComponentType<{ className?: string; strokeWidth?: number; style?: CSSProperties }>> = {
  BarChart3,
  Fingerprint,
  ShieldCheck,
};

export default function VerificationEcosystem() {
  return (
    <section
      id="ecosystem"
      className="py-24 lg:py-32"
      style={{ backgroundColor: "var(--brand-surface-low)" }}
    >
      <div className="max-w-7xl mx-auto px-6 lg:px-8">
        {/* Section header */}
        <div className="mb-16">
          <div
            className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-widest mb-4"
            style={{
              backgroundColor: "rgba(63,102,83,0.08)",
              color: "var(--brand-viridian)",
              border: "1px solid rgba(63,102,83,0.15)",
            }}
          >
            Platform Primitives
          </div>
          <h2
            className="text-4xl md:text-5xl font-extrabold editorial-spacing font-display leading-tight mb-4"
            style={{ color: "var(--brand-navy)" }}
          >
            The Verification Ecosystem
          </h2>
          {/* Accent line */}
          <div
            className="h-1 w-20 rounded-full"
            style={{ background: "var(--brand-viridian)" }}
          />
        </div>

        {/* Feature cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {ecosystemFeatures.map((feature, idx) => {
            const Icon = iconMap[feature.icon] ?? ShieldCheck;
            return (
              <div
                key={feature.title}
                className="bg-white rounded-2xl p-10 group transition-all duration-300 hover:-translate-y-1 landing-card"
                style={{
                  border: "1px solid rgba(196,198,207,0.1)",
                  transitionTimingFunction: "cubic-bezier(0.16, 1, 0.3, 1)",
                }}
              >
                {/* Icon container */}
                <div
                  className="w-14 h-14 rounded-xl flex items-center justify-center mb-8 transition-colors duration-300 group-hover:bg-opacity-30"
                  style={{
                    backgroundColor: "rgba(63,102,83,0.08)",
                    border: "1px solid rgba(63,102,83,0.12)",
                  }}
                >
                  <Icon
                    className="w-7 h-7"
                    strokeWidth={1.5}
                    style={{ color: "var(--brand-viridian)" }}
                  />
                </div>

                {/* Step number — subtle */}
                <div
                  className="text-xs font-bold uppercase tracking-widest mb-3"
                  style={{ color: "rgba(63,102,83,0.5)" }}
                >
                  0{idx + 1}
                </div>

                <h3
                  className="text-2xl font-bold font-display editorial-spacing mb-4"
                  style={{ color: "var(--brand-navy)" }}
                >
                  {feature.title}
                </h3>
                <p
                  className="leading-relaxed text-[15px]"
                  style={{ color: "var(--brand-on-surface-variant)" }}
                >
                  {feature.description}
                </p>

                {/* Hover accent line */}
                <div
                  className="mt-8 h-0.5 w-0 rounded-full transition-all duration-300 group-hover:w-12"
                  style={{ background: "var(--brand-viridian)" }}
                />
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
