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
      className="py-24 lg:py-32 bg-brand-surface-low"
    >
      <div className="max-w-7xl mx-auto px-6 lg:px-8">
        {/* Section header */}
        <div className="mb-16">
          <div
            className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-widest mb-4 bg-brand-viridian/8 text-brand-viridian border border-brand-viridian/15"
          >
            How verification works
          </div>
          <h2
            className="text-4xl md:text-5xl font-extrabold editorial-spacing font-display leading-tight mb-4 text-brand-navy"
          >
            Three things you get with every verified property.
          </h2>
          {/* Accent line */}
          <div
            className="h-1 w-20 rounded-full bg-brand-viridian"
          />
        </div>

        {/* Feature cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {ecosystemFeatures.map((feature, idx) => {
            const Icon = iconMap[feature.icon] ?? ShieldCheck;
            return (
              <div
                key={feature.title}
                className="bg-white rounded-2xl p-10 group transition-all duration-300 hover:-translate-y-1 landing-card border border-brand-outline-variant/10 ease-[cubic-bezier(0.16,1,0.3,1)]"
              >
                {/* Icon container */}
                <div
                  className="w-14 h-14 rounded-xl flex items-center justify-center mb-8 transition-colors duration-300 group-hover:bg-opacity-30 bg-brand-viridian/8 border border-brand-viridian/12"
                >
                  <Icon
                    className="w-7 h-7 text-brand-viridian"
                    strokeWidth={1.5}
                  />
                </div>

                {/* Step number — subtle */}
                <div
                  className="text-xs font-bold uppercase tracking-widest mb-3 text-brand-viridian"
                >
                  0{idx + 1}
                </div>

                <h3
                  className="text-2xl font-bold font-display editorial-spacing mb-4 text-brand-navy"
                >
                  {feature.title}
                </h3>
                <p
                  className="leading-relaxed text-[15px] text-brand-on-surface-variant"
                >
                  {feature.description}
                </p>

                {/* Hover accent line */}
                <div
                  className="mt-8 h-0.5 w-0 rounded-full transition-all duration-300 group-hover:w-12 bg-brand-viridian"
                />
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
