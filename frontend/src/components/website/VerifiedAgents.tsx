import type { ComponentType, CSSProperties } from "react";
import Link from "next/link";
import { MapPin, Ruler, FileText, Scale, CheckCircle2, ArrowRight } from "lucide-react";
import { agentTypes, CTA_AGENT_HREF } from "./home.data";

const iconMap: Record<string, ComponentType<{ className?: string; strokeWidth?: number; style?: CSSProperties }>> = {
  MapPin,
  Ruler,
  FileText,
  Scale,
};

export default function VerifiedAgents() {
  return (
    <section
      id="agents"
      className="py-24 lg:py-32"
      style={{ backgroundColor: "var(--brand-surface-low)" }}
    >
      <div className="max-w-7xl mx-auto px-6 lg:px-8">
        {/* Header row */}
        <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-8 mb-16">
          <div>
            <div
              className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-widest mb-4"
              style={{
                backgroundColor: "rgba(63,102,83,0.08)",
                color: "var(--brand-viridian)",
                border: "1px solid rgba(63,102,83,0.15)",
              }}
            >
              Certified Network
            </div>
            <h2
              className="text-4xl md:text-5xl font-extrabold editorial-spacing font-display leading-tight"
              style={{ color: "var(--brand-navy)" }}
            >
              Verified Agents
            </h2>
            <div
              className="h-1 w-20 rounded-full mt-4"
              style={{ background: "var(--brand-viridian)" }}
            />
          </div>
          <p
            className="max-w-md text-[15px] leading-relaxed"
            style={{ color: "var(--brand-on-surface-variant)" }}
          >
            Every verification is handled by KYC-approved independent professionals.
            All agents are screened, licensed where applicable, and performance-rated.
          </p>
        </div>

        {/* Agent cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {agentTypes.map((agent, idx) => {
            const Icon = iconMap[agent.icon] ?? Scale;
            return (
              <div
                key={agent.name}
                className="bg-white rounded-2xl p-8 group transition-all duration-300 hover:-translate-y-1 relative overflow-hidden"
                style={{
                  border: "1px solid rgba(196,198,207,0.1)",
                  boxShadow: "0 2px 8px rgba(0,13,34,0.04)",
                  transitionTimingFunction: "cubic-bezier(0.16, 1, 0.3, 1)",
                }}
              >
                {/* Subtle index number — decorative */}
                <div
                  className="absolute top-4 right-5 text-5xl font-extrabold font-display pointer-events-none select-none"
                  style={{ color: "rgba(0,13,34,0.04)" }}
                >
                  0{idx + 1}
                </div>

                {/* Icon */}
                <div
                  className="w-12 h-12 rounded-xl flex items-center justify-center mb-6"
                  style={{
                    background: "linear-gradient(135deg, rgba(63,102,83,0.1) 0%, rgba(63,102,83,0.06) 100%)",
                    border: "1px solid rgba(63,102,83,0.15)",
                  }}
                >
                  <Icon
                    className="w-6 h-6"
                    strokeWidth={1.5}
                    style={{ color: "var(--brand-viridian)" }}
                  />
                </div>

                <h3
                  className="text-lg font-bold font-display mb-2"
                  style={{ color: "var(--brand-navy)" }}
                >
                  {agent.name}
                </h3>
                <p
                  className="text-sm leading-relaxed mb-6"
                  style={{ color: "var(--brand-on-surface-variant)" }}
                >
                  {agent.description}
                </p>

                {/* Responsibilities */}
                <ul className="space-y-2">
                  {agent.responsibilities.map((r) => (
                    <li
                      key={r}
                      className="flex items-start gap-2 text-xs"
                      style={{ color: "var(--brand-on-surface-variant)" }}
                    >
                      <CheckCircle2
                        className="w-3.5 h-3.5 mt-0.5 flex-shrink-0"
                        strokeWidth={2}
                        style={{ color: "var(--brand-viridian)" }}
                      />
                      {r}
                    </li>
                  ))}
                </ul>

                {/* Hover bottom accent */}
                <div
                  className="absolute bottom-0 inset-x-0 h-0.5 opacity-0 transition-all duration-300 group-hover:h-1 group-hover:opacity-100"
                  style={{ background: "var(--brand-viridian)" }}
                />
              </div>
            );
          })}
        </div>

        {/* Become an agent CTA */}
        <div className="mt-14 text-center">
          <div
            className="text-sm mb-4"
            style={{ color: "var(--brand-on-surface-variant)" }}
          >
            Are you a field agent, surveyor, registry official, or property lawyer in Nigeria?
          </div>
          <Link
            href={CTA_AGENT_HREF}
            className="inline-flex items-center gap-2 px-8 py-3.5 rounded-xl font-semibold text-sm transition-all duration-200 hover:opacity-90 hover:scale-[0.98] group"
            style={{
              color: "var(--brand-viridian)",
              border: "2px solid var(--brand-viridian)",
              backgroundColor: "rgba(63,102,83,0.04)",
            }}
          >
            Become a Verified Agent
            <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
          </Link>
        </div>
      </div>
    </section>
  );
}
