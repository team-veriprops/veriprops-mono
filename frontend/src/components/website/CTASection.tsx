import Link from "next/link";
import { ArrowRight, CheckCircle2, Shield, Users } from "lucide-react";

export default function CTASection() {
  return (
    <section className="py-24 lg:py-32">
      <div className="max-w-7xl mx-auto px-6 lg:px-8">
        <div
          className="relative rounded-3xl overflow-hidden px-10 py-16 md:px-20 md:py-24"
          style={{
            background: "linear-gradient(135deg, var(--brand-navy) 0%, var(--brand-navy-mid) 50%, var(--brand-navy-deep) 100%)",
          }}
        >
          {/* Background grid pattern */}
          <div
            className="absolute inset-0 pointer-events-none"
            style={{
              backgroundImage:
                "radial-gradient(circle at 1px 1px, rgba(255,255,255,0.04) 1px, transparent 0)",
              backgroundSize: "40px 40px",
            }}
          />

          {/* Ambient glow */}
          <div
            className="absolute top-0 right-0 w-[500px] h-[500px] rounded-full pointer-events-none"
            style={{
              background: "radial-gradient(circle, rgba(63,102,83,0.15) 0%, transparent 70%)",
              transform: "translate(30%, -30%)",
            }}
          />
          <div
            className="absolute bottom-0 left-0 w-[400px] h-[400px] rounded-full pointer-events-none"
            style={{
              background: "radial-gradient(circle, rgba(190,234,209,0.06) 0%, transparent 70%)",
              transform: "translate(-30%, 30%)",
            }}
          />

          <div className="relative z-10 flex flex-col lg:flex-row items-start lg:items-center justify-between gap-12">
            {/* Left — copy */}
            <div className="lg:max-w-[55%]">
              {/* Trust badge */}
              <div
                className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-bold uppercase tracking-widest mb-8"
                style={{
                  backgroundColor: "rgba(63,102,83,0.2)",
                  color: "#a5d0b9",
                  border: "1px solid rgba(63,102,83,0.3)",
                }}
              >
                <CheckCircle2 className="w-3.5 h-3.5" />
                ✅ Veriprops Verified
              </div>

              <h2
                className="text-4xl md:text-5xl font-extrabold editorial-spacing font-display leading-[1.1] text-white mb-6"
              >
                Your legacy is too valuable{" "}
                <span style={{ color: "#a5d0b9" }}>to risk on hearsay.</span>
              </h2>

              <p className="text-lg leading-relaxed mb-10 text-white/70 max-w-lg">
                Veriprops provides the sovereign certainty required to build
                generational wealth in Nigeria — from anywhere in the world.
                Verify everything. Trust nothing blindly.
              </p>

              {/* Disclaimer */}
              <div
                className="text-xs leading-relaxed mb-10 px-4 py-3 rounded-xl"
                style={{
                  backgroundColor: "rgba(255,255,255,0.06)",
                  color: "rgba(255,255,255,0.5)",
                  border: "1px solid rgba(255,255,255,0.08)",
                }}
              >
                We reduce uncertainty. We do not eliminate it. Reports represent professional
                opinions at the time of verification — not legal guarantees.
              </div>

              {/* CTAs */}
              <div className="flex flex-col sm:flex-row gap-4">
                <Link
                  href="/auth/login?intent=verify"
                  className="group inline-flex items-center justify-center gap-2.5 px-10 py-4 rounded-xl font-bold text-base transition-all duration-200 hover:opacity-90 hover:scale-[0.98]"
                  style={{
                    backgroundColor: "var(--brand-viridian)",
                    color: "#fff",
                    boxShadow: "0 8px 24px -4px rgba(63,102,83,0.5)",
                  }}
                >
                  Verify a Property Now
                  <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
                </Link>
                <Link
                  href="/auth/login?intent=agent"
                  className="inline-flex items-center justify-center gap-2 px-10 py-4 rounded-xl font-bold text-base transition-all duration-200 hover:bg-white/10"
                  style={{
                    color: "#fff",
                    border: "1px solid rgba(255,255,255,0.2)",
                  }}
                >
                  Become an Agent
                </Link>
              </div>
            </div>

            {/* Right — trust proof cards */}
            <div className="flex flex-col gap-4 w-full lg:max-w-[280px]">
              {[
                {
                  icon: Shield,
                  title: "Process Integrity",
                  body: "Qualified agents, required steps per tier — we are accountable for every verification.",
                },
                {
                  icon: CheckCircle2,
                  title: "Accurate Findings",
                  body: "Reports reflect exactly what agents submitted — nothing distorted.",
                },
                {
                  icon: Users,
                  title: "All Communications On-Platform",
                  body: "Every message, every document — recorded, auditable, secure.",
                },
              ].map(({ icon: Icon, title, body }) => (
                <div
                  key={title}
                  className="flex items-start gap-4 p-5 rounded-2xl"
                  style={{
                    backgroundColor: "rgba(255,255,255,0.06)",
                    border: "1px solid rgba(255,255,255,0.08)",
                  }}
                >
                  <div
                    className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0"
                    style={{ backgroundColor: "rgba(63,102,83,0.25)" }}
                  >
                    <Icon className="w-4.5 h-4.5 text-white/80" strokeWidth={1.5} />
                  </div>
                  <div>
                    <div className="text-sm font-bold text-white mb-1">{title}</div>
                    <div className="text-xs leading-relaxed text-white/60">{body}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
