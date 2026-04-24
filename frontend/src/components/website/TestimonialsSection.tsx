import { Quote } from "lucide-react";
import { testimonials } from "./home.data";

const tierColors: Record<string, { bg: string; text: string }> = {
  Premium: { bg: "rgba(115,92,0,0.1)", text: "var(--brand-gold)" },
  Standard: { bg: "rgba(63,102,83,0.1)", text: "var(--brand-viridian)" },
  Basic: { bg: "rgba(0,13,34,0.06)", text: "var(--brand-navy)" },
};

export default function TestimonialsSection() {
  return (
    <section
      id="testimonials"
      className="py-24 lg:py-32"
      style={{ backgroundColor: "var(--brand-surface-low)" }}
    >
      <div className="max-w-7xl mx-auto px-6 lg:px-8">
        {/* Header */}
        <div className="text-center mb-16">
          <div
            className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-widest mb-4"
            style={{
              backgroundColor: "rgba(63,102,83,0.08)",
              color: "var(--brand-viridian)",
              border: "1px solid rgba(63,102,83,0.15)",
            }}
          >
            Client Stories
          </div>
          <h2
            className="text-4xl md:text-5xl font-extrabold editorial-spacing font-display leading-tight"
            style={{ color: "var(--brand-navy)" }}
          >
            Trusted by Nigerians{" "}
            <span style={{ color: "var(--brand-viridian)" }}>Worldwide</span>
          </h2>
        </div>

        {/* Testimonial cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {testimonials.map((t) => {
            const tierStyle = tierColors[t.tier] ?? tierColors.Basic;
            return (
              <div
                key={t.name}
                className="bg-white rounded-2xl p-8 flex flex-col group hover:-translate-y-1 transition-all duration-300 landing-card"
                style={{
                  border: "1px solid rgba(196,198,207,0.1)",
                  transitionTimingFunction: "cubic-bezier(0.16, 1, 0.3, 1)",
                }}
              >
                {/* Quote icon */}
                <Quote
                  className="w-8 h-8 mb-6 flex-shrink-0"
                  strokeWidth={1.5}
                  style={{ color: "rgba(63,102,83,0.3)" }}
                />

                {/* Quote text */}
                <p
                  className="text-[15px] leading-relaxed flex-1 mb-8"
                  style={{ color: "var(--brand-on-surface)" }}
                >
                  &ldquo;{t.quote}&rdquo;
                </p>

                {/* Author */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    {/* Avatar */}
                    <div
                      className="w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold font-display"
                      style={{
                        background: "linear-gradient(135deg, var(--brand-navy) 0%, var(--brand-navy-deep) 100%)",
                        color: "#fff",
                      }}
                    >
                      {t.initials}
                    </div>
                    <div>
                      <div
                        className="text-sm font-bold"
                        style={{ color: "var(--brand-navy)" }}
                      >
                        {t.name}
                      </div>
                      <div className="text-xs" style={{ color: "var(--brand-on-surface-variant)" }}>
                        {t.location}
                      </div>
                    </div>
                  </div>

                  {/* Tier badge */}
                  <div
                    className="px-2.5 py-1 rounded-full text-xs font-semibold"
                    style={{ backgroundColor: tierStyle.bg, color: tierStyle.text }}
                  >
                    {t.tier}
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Bottom stats bar */}
        <div
          className="mt-16 grid grid-cols-3 divide-x rounded-2xl overflow-hidden"
          style={{
            backgroundColor: "#fff",
            border: "1px solid rgba(196,198,207,0.15)",
            boxShadow: "0 4px 16px rgba(0,13,34,0.04)",
          }}
        >
          {[
            { value: "2,400+", label: "Properties verified" },
            { value: "98%", label: "Client satisfaction rate" },
            { value: "£65k+", label: "Avg. transaction protected" },
          ].map((stat) => (
            <div key={stat.label} className="py-8 px-6 text-center" style={{ borderColor: "rgba(196,198,207,0.2)" }}>
              <div
                className="text-3xl font-extrabold font-display editorial-spacing mb-1"
                style={{ color: "var(--brand-navy)" }}
              >
                {stat.value}
              </div>
              <div className="text-sm" style={{ color: "var(--brand-on-surface-variant)" }}>
                {stat.label}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
