import Link from "next/link";
import { CheckCircle2, ArrowRight, TrendingUp } from "lucide-react";
import { CTA_VERIFY_HREF } from "./home.data";

export default function HeroSection() {
  return (
    <section
      className="relative min-h-screen flex items-center overflow-hidden pt-20"
      style={{ backgroundColor: "#ffffff" }}
    >
      {/* Subtle background grid */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          backgroundImage:
            "radial-gradient(circle at 1px 1px, rgba(0,13,34,0.04) 1px, transparent 0)",
          backgroundSize: "40px 40px",
        }}
      />

      {/* Warm ambient glow — top right */}
      <div
        className="absolute -top-32 -right-32 w-[600px] h-[600px] rounded-full pointer-events-none"
        style={{
          background:
            "radial-gradient(circle, rgba(63,102,83,0.06) 0%, transparent 70%)",
        }}
      />

      <div className="relative max-w-7xl mx-auto px-6 lg:px-8 w-full grid grid-cols-1 lg:grid-cols-2 gap-16 items-center py-16 lg:py-24">
        {/* Left — Copy */}
        <div className="z-10 animate-fade-up">
          {/* Trust pill */}
          <div
            className="inline-flex items-center gap-2 px-4 py-2 rounded-full mb-8 text-xs font-semibold uppercase tracking-widest"
            style={{
              backgroundColor: "rgba(63,102,83,0.08)",
              color: "var(--brand-viridian)",
              border: "1px solid rgba(63,102,83,0.15)",
            }}
          >
            <CheckCircle2 className="w-3.5 h-3.5" strokeWidth={2.5} />
            Trusted by Global Diaspora
          </div>

          <h1
            className="text-5xl md:text-6xl lg:text-[4.25rem] font-extrabold editorial-spacing font-display leading-[1.08] mb-7"
            style={{ color: "var(--brand-navy)" }}
          >
            Secure Your{" "}
            <span
              className="relative inline-block"
              style={{ color: "var(--brand-viridian)" }}
            >
              Nigerian
              {/* Underline accent */}
              <span
                className="absolute -bottom-1 left-0 right-0 h-[3px] rounded-full"
                style={{ background: "var(--brand-viridian)", opacity: 0.4 }}
              />
            </span>
            <br />
            Real Estate Future
          </h1>

          <p
            className="text-lg md:text-xl leading-relaxed mb-10 max-w-[480px]"
            style={{ color: "var(--brand-on-surface-variant)" }}
          >
            Eliminate fraud and uncertainty with rigorously verified property
            data. Protect your family&apos;s wealth from anywhere in the world —
            we verify before you pay.
          </p>

          {/* Trust stats row */}
          <div className="flex items-center gap-8 mb-10">
            {[
              { value: "2,400+", label: "Properties Verified" },
              { value: "98%", label: "Accuracy Rate" },
              { value: "4 Roles", label: "Certified Agents" },
            ].map((stat) => (
              <div key={stat.label} className="text-center">
                <div
                  className="text-xl font-bold font-display editorial-spacing"
                  style={{ color: "var(--brand-navy)" }}
                >
                  {stat.value}
                </div>
                <div className="text-xs font-medium mt-0.5" style={{ color: "var(--brand-on-surface-variant)" }}>
                  {stat.label}
                </div>
              </div>
            ))}
          </div>

          {/* CTAs */}
          <div className="flex flex-col sm:flex-row gap-4">
            <Link
              href={CTA_VERIFY_HREF}
              className="group inline-flex items-center justify-center gap-2.5 signature-gradient text-white px-8 py-4 rounded-xl text-base font-bold transition-all duration-200 hover:opacity-90 hover:scale-[0.98] active:scale-95"
              style={{ boxShadow: "0 8px 24px -4px rgba(0,13,34,0.35)" }}
            >
              Start Verification
              <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
            </Link>
            <a
              href="#sample"
              className="inline-flex items-center justify-center gap-2 px-8 py-4 rounded-xl text-base font-bold transition-all duration-200 hover:bg-gray-50"
              style={{
                color: "var(--brand-navy)",
                border: "1px solid rgba(196,198,207,0.4)",
              }}
            >
              View Sample Report
            </a>
          </div>
        </div>

        {/* Right — Property Visual */}
        <div className="relative hidden lg:block animate-fade-up stagger-2">
          {/* Main card — building photo */}
          <div
            className="relative rounded-2xl overflow-hidden"
            style={{
              aspectRatio: "4/5",
              boxShadow: "0 40px 80px -20px rgba(0,13,34,0.4), 0 20px 40px -10px rgba(0,13,34,0.2)",
            }}
          >
            {/* Building photo */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="https://lh3.googleusercontent.com/aida-public/AB6AXuAO_Eq5vDmcaofv3N4Q_Amj9Crd55fK23KCGojQWeOYWjNv8tbaDH1Eh5IiOCHtVPoFcbLFPYKsVIoU77rFIw31qIl5eSxg5YHpRMXtT7oX4G80w2QOJ6vGmf__Cq3MGpaHjqZ3Zk-N-zwPdd733mz5gtwLmtI-cHIWtvojaAxkg3ALvtbBI2aFrImZY3bBO1DA-78_UxBkgswpTwgebrzSxqUUHvl3WFpY12gpF3PFkt1KQF8vY0T7QF8iKRTGmk4aVtwukfYFs3U"
              alt="Modern luxury property in Lagos Nigeria"
              className="w-full h-full object-cover"
            />

            {/* Top-left: property ID chip */}
            <div
              className="absolute top-6 left-6 px-3 py-1.5 rounded-full text-xs font-mono font-semibold"
              style={{
                background: "rgba(255,255,255,0.1)",
                backdropFilter: "blur(12px)",
                color: "rgba(255,255,255,0.8)",
                border: "1px solid rgba(255,255,255,0.12)",
              }}
            >
              VP-2025-LAG-00847
            </div>

            {/* Verified badge — top right */}
            <div
              className="absolute top-6 right-6 flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-bold"
              style={{
                background: "rgba(63,102,83,0.3)",
                backdropFilter: "blur(12px)",
                color: "#a5d0b9",
                border: "1px solid rgba(63,102,83,0.4)",
              }}
            >
              <CheckCircle2 className="w-3.5 h-3.5" />
              Verified
            </div>

            {/* Bottom bar — property meta */}
            <div
              className="absolute bottom-0 inset-x-0 px-6 py-5"
              style={{
                background: "linear-gradient(to top, rgba(0,13,34,0.7) 0%, transparent 100%)",
              }}
            >
              {/* <div className="text-white/60 text-xs font-medium mb-1">Lekki Phase 1, Lagos</div>
              <div className="text-white text-sm font-semibold">2,400 sqm · C of O Verified</div> */}
            </div>
          </div>

          {/* Floating Trust Score card */}
          <div
            className="absolute -bottom-10 -left-10 glass-card rounded-2xl p-6 w-64 animate-float"
            style={{ boxShadow: "0 24px 48px rgba(0,13,34,0.12)" }}
          >
            <div className="flex items-center gap-4 mb-4">
              {/* Score ring */}
              <div className="relative flex-shrink-0">
                <svg width="56" height="56" viewBox="0 0 56 56" className="-rotate-90">
                  <circle cx="28" cy="28" r="22" fill="none" stroke="rgba(196,198,207,0.3)" strokeWidth="4" />
                  <circle
                    cx="28"
                    cy="28"
                    r="22"
                    fill="none"
                    stroke="var(--brand-viridian)"
                    strokeWidth="4"
                    strokeLinecap="round"
                    strokeDasharray={`${2 * Math.PI * 22 * 0.92} ${2 * Math.PI * 22}`}
                  />
                </svg>
                <div
                  className="absolute inset-0 flex items-center justify-center text-sm font-bold font-display"
                  style={{ color: "var(--brand-navy)" }}
                >
                  92
                </div>
              </div>
              <div>
                <div
                  className="text-xs font-bold uppercase tracking-wider"
                  style={{ color: "var(--brand-viridian)" }}
                >
                  Trust Score
                </div>
                <div className="text-sm font-medium mt-0.5" style={{ color: "var(--brand-on-surface-variant)" }}>
                  Property Safe
                </div>
              </div>
            </div>
            {/* Score bars */}
            <div className="flex gap-1">
              {[1, 1, 1, 1, 0.4].map((opacity, i) => (
                <div
                  key={i}
                  className="h-1 flex-1 rounded-full"
                  style={{ background: `rgba(63,102,83,${opacity})` }}
                />
              ))}
            </div>
            <div className="mt-2 flex items-center gap-1.5">
              <TrendingUp className="w-3 h-3" style={{ color: "var(--brand-viridian)" }} />
              <span className="text-xs" style={{ color: "var(--brand-on-surface-variant)" }}>
                Above caution threshold
              </span>
            </div>
          </div>

          {/* Floating SLA chip — top right of card */}
          <div
            className="absolute -top-5 -right-5 flex items-center gap-2 px-4 py-2.5 rounded-full text-sm font-semibold shadow-lg"
            style={{
              backgroundColor: "#fff",
              color: "var(--brand-viridian)",
              border: "1px solid rgba(63,102,83,0.2)",
              boxShadow: "0 8px 24px rgba(0,13,34,0.1)",
            }}
          >
            <span className="w-2 h-2 rounded-full animate-pulse-soft" style={{ backgroundColor: "var(--brand-viridian)" }} />
            Report in 5–7 days
          </div>
        </div>
      </div>

      {/* Bottom wave divider */}
      <div className="absolute bottom-0 inset-x-0 h-16 pointer-events-none">
        <svg viewBox="0 0 1440 64" fill="none" className="w-full h-full" preserveAspectRatio="none">
          <path
            d="M0 64L480 16L960 48L1440 8V64H0Z"
            fill="var(--brand-surface-low)"
          />
        </svg>
      </div>
    </section>
  );
}
