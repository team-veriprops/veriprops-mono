import { Quote } from "lucide-react";
import { testimonials } from "./home.data";

const tierClasses: Record<string, string> = {
  Premium: "bg-brand-gold/10 text-brand-gold",
  Standard: "bg-brand-viridian/10 text-brand-viridian",
  Basic: "bg-brand-navy/6 text-brand-navy",
};

export default function TestimonialsSection() {
  return (
    <section
      id="testimonials"
      className="py-24 lg:py-32 bg-brand-surface-low"
    >
      <div className="max-w-7xl mx-auto px-6 lg:px-8">
        {/* Header */}
        <div className="text-center mb-16">
          <div
            className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-widest mb-4 bg-brand-viridian/8 text-brand-viridian border border-brand-viridian/15"
          >
            Client Stories
          </div>
          <h2
            className="text-4xl md:text-5xl font-extrabold editorial-spacing font-display leading-tight text-brand-navy"
          >
            Trusted by Nigerians{" "}
            <span className="text-brand-viridian">Worldwide</span>
          </h2>
        </div>

        {/* Testimonial cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {testimonials.map((t) => {
            const tierClass = tierClasses[t.tier] ?? tierClasses.Basic;
            return (
              <div
                key={t.name}
                className="bg-white rounded-2xl p-8 flex flex-col group hover:-translate-y-1 transition-all duration-300 landing-card border border-brand-outline-variant/10 ease-[cubic-bezier(0.16,1,0.3,1)]"
              >
                {/* Quote icon */}
                <Quote
                  className="w-8 h-8 mb-6 flex-shrink-0 text-brand-viridian/30"
                  strokeWidth={1.5}
                />

                {/* Quote text */}
                <p
                  className="text-[15px] leading-relaxed flex-1 mb-8 text-brand-on-surface"
                >
                  &ldquo;{t.quote}&rdquo;
                </p>

                {/* Author */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    {/* Avatar */}
                    <div
                      className="w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold font-display signature-gradient text-white"
                    >
                      {t.initials}
                    </div>
                    <div>
                      <div
                        className="text-sm font-bold text-brand-navy"
                      >
                        {t.name}
                      </div>
                      <div className="text-xs text-brand-on-surface-variant">
                        {t.location}
                      </div>
                    </div>
                  </div>

                  {/* Tier badge */}
                  <div
                    className={`px-2.5 py-1 rounded-full text-xs font-semibold ${tierClass}`}
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
          className="mt-16 grid grid-cols-3 divide-x rounded-2xl overflow-hidden bg-white border border-brand-outline-variant/15 shadow-[0_4px_16px_rgba(0,13,34,0.04)]"
        >
          {[
            { value: "2,400+", label: "Properties verified" },
            { value: "98%", label: "Client satisfaction rate" },
            { value: "£65k+", label: "Avg. transaction protected" },
          ].map((stat) => (
            <div key={stat.label} className="py-8 px-6 text-center border-brand-outline-variant/20">
              <div
                className="text-3xl font-extrabold font-display editorial-spacing mb-1 text-brand-navy"
              >
                {stat.value}
              </div>
              <div className="text-sm text-brand-on-surface-variant">
                {stat.label}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
