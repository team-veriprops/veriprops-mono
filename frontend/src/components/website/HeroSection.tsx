import Link from "next/link";
import { CheckCircle2, ArrowRight, TrendingUp } from "lucide-react";
import { CTA_VERIFY_HREF } from "./home.data";
import { ROUTES } from "@lib/routes";

export default function HeroSection() {
  return (
    <section
      className="relative min-h-screen flex items-center overflow-hidden pt-20 bg-white"
    >
      {/* Subtle background grid */}
      <div
        className="absolute inset-0 pointer-events-none bg-[radial-gradient(circle_at_1px_1px,rgba(0,13,34,0.04)_1px,transparent_0)] bg-size-[40px_40px]"
      />

      {/* Warm ambient glow — top right */}
      <div
        className="absolute -top-32 -right-32 w-[600px] h-[600px] rounded-full pointer-events-none bg-[radial-gradient(circle,rgba(63,102,83,0.06)_0%,transparent_70%)]"
      />

      <div className="relative max-w-7xl mx-auto px-6 lg:px-8 w-full grid grid-cols-1 lg:grid-cols-2 gap-16 items-center py-16 lg:py-24">
        {/* Left — Copy */}
        <div className="z-10 animate-fade-up">
          {/* Trust pill */}
          <div
            className="inline-flex items-center gap-2 px-4 py-2 rounded-full mb-8 text-xs font-semibold uppercase tracking-widest bg-brand-viridian/8 text-brand-viridian border border-brand-viridian/15"
          >
            <CheckCircle2 className="w-3.5 h-3.5" strokeWidth={2.5} />
            Trusted by Nigerians worldwide
          </div>

          <h1
          className="text-5xl md:text-6xl lg:text-[4.25rem] font-extrabold editorial-spacing font-display leading-[1.08] mb-7 text-brand-navy"
            >
              Buy property in Nigeria with
              <em
              className="relative inline-block text-brand-viridian"
              >
                certainty
                {/* Underline accent */}
                <span
                  className="absolute -bottom-1 left-0 right-0 h-0.75 rounded-full bg-brand-viridian/40"
                >
                </span>
              </em>
              <br />
              — from anywhere in the world.
          </h1>

          <p
            className="text-lg md:text-xl leading-relaxed mb-10 max-w-[480px] text-brand-on-surface-variant"
          >
            Before you send a single naira, we confirm the ownership, the boundaries, 
            the documents, and the truth on the ground. You see exactly what you&rsquo;re
            buying. Then you decide.
          </p>

          {/* Trust stats row */}
          <div className="flex items-center gap-8 mb-10">
            {[
              { value: "2,400+", label: "Properties Verified" },
              { value: "98%", label: "Accuracy Rate" },
              { value: "£4.1M+", label: "Buyer funds protected" },
              { value: "1 in 6", label: "Listings flagged with a problem" },
            ].map((stat) => (
              <div key={stat.label} className="text-center">
                <div
                  className="text-xl font-bold font-display editorial-spacing text-brand-navy"
                >
                  {stat.value}
                </div>
                <div className="text-xs font-medium mt-0.5 text-brand-on-surface-variant">
                  {stat.label}
                </div>
              </div>
            ))}
          </div>

          {/* CTAs */}
          <div className="flex flex-col sm:flex-row gap-4">
            <Link
              href={CTA_VERIFY_HREF}
              className="group inline-flex items-center justify-center gap-2.5 signature-gradient text-white px-8 py-4 rounded-xl text-base font-bold transition-all duration-200 hover:opacity-90 hover:scale-[0.98] active:scale-95 shadow-[0_8px_24px_-4px_rgba(0,13,34,0.35)]"
            >
              Start Verification
              <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
            </Link>
            <Link
              href={ROUTES.SAMPLE_REPORT}
              className="inline-flex items-center justify-center gap-2 px-8 py-4 rounded-xl text-base font-bold transition-all duration-200 hover:bg-gray-50 text-brand-navy border border-brand-outline-variant/40"
            >
              View Sample Report
            </Link>
          </div>
        </div>

        {/* Right — Property Visual */}
        <div className="relative hidden lg:block animate-fade-up stagger-2">
          {/* Main card — building photo */}
          <div
            className="relative rounded-2xl overflow-hidden aspect-4/5 shadow-[0_40px_80px_-20px_rgba(0,13,34,0.4),0_20px_40px_-10px_rgba(0,13,34,0.2)]"
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
              className="absolute top-6 left-6 px-3 py-1.5 rounded-full text-xs font-mono font-semibold bg-white/10 backdrop-blur-md text-white/80 border border-white/12"
            >
              VP-2025-LAG-00847
            </div>

            {/* Verified badge — top right */}
            <div
              className="absolute top-6 right-6 flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-bold bg-brand-viridian/30 backdrop-blur-md text-sidebar-accent-foreground border border-brand-viridian/40"
            >
              <CheckCircle2 className="w-3.5 h-3.5" />
              Verified
            </div>

            {/* Bottom bar — property meta */}
            <div
              className="absolute bottom-0 inset-x-0 px-6 py-5 bg-[linear-gradient(to_top,rgba(0,13,34,0.7)_0%,transparent_100%)]"
            >
              {/* <div className="text-white/60 text-xs font-medium mb-1">Lekki Phase 1, Lagos</div>
              <div className="text-white text-sm font-semibold">2,400 sqm · C of O Verified</div> */}
            </div>
          </div>

          {/* Floating Trust Score card */}
          <div
            className="absolute -bottom-10 -left-10 glass-card rounded-2xl p-6 w-64 animate-float shadow-[0_24px_48px_rgba(0,13,34,0.12)]"
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
                  className="absolute inset-0 flex items-center justify-center text-sm font-bold font-display text-brand-navy"
                >
                  92
                </div>
              </div>
              <div>
                <div
                  className="text-xs font-bold uppercase tracking-wider text-brand-viridian"
                >
                  Trust Score
                </div>
                <div className="text-sm font-medium mt-0.5 text-brand-on-surface-variant">
                  Property Safe
                </div>
              </div>
            </div>
            {/* Score bars */}
            <div className="flex gap-1">
              {["bg-brand-viridian", "bg-brand-viridian", "bg-brand-viridian", "bg-brand-viridian", "bg-brand-viridian/40"].map((barClass, i) => (
                <div
                  key={i}
                  className={`h-1 flex-1 rounded-full ${barClass}`}
                />
              ))}
            </div>
            <div className="mt-2 flex items-center gap-1.5">
              <TrendingUp className="w-3 h-3 text-brand-viridian" />
              <span className="text-xs text-brand-on-surface-variant">
                Above caution threshold
              </span>
            </div>
          </div>

          {/* Floating SLA chip — top right of card */}
          <div
            className="absolute -top-5 -right-5 flex items-center gap-2 px-4 py-2.5 rounded-full text-sm font-semibold bg-white text-brand-viridian border border-brand-viridian/20 shadow-[0_8px_24px_rgba(0,13,34,0.1)]"
          >
            <span className="w-2 h-2 rounded-full animate-pulse-soft bg-brand-viridian" />
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
