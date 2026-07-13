import Link from "next/link";
import { ArrowRight, CheckCircle2, Shield, Users } from "lucide-react";
import { CTA_VERIFY_HREF, CTA_AGENT_HREF } from "./home.data";

export default function CTASection() {
  return (
    <section className="py-24 lg:py-32">
      <div className="max-w-7xl mx-auto px-6 lg:px-8">
        <div
          className="relative rounded-3xl overflow-hidden px-10 py-16 md:px-20 md:py-24 bg-[linear-gradient(135deg,var(--brand-navy)_0%,var(--brand-navy-mid)_50%,var(--brand-navy-deep)_100%)]"
        >
          {/* Background grid pattern */}
          <div
            className="absolute inset-0 pointer-events-none bg-[radial-gradient(circle_at_1px_1px,rgba(255,255,255,0.04)_1px,transparent_0)] bg-size-[40px_40px]"
          />

          {/* Ambient glow */}
          <div
            className="absolute top-0 right-0 w-[500px] h-[500px] rounded-full pointer-events-none bg-[radial-gradient(circle,rgba(63,102,83,0.15)_0%,transparent_70%)] translate-x-[30%] translate-y-[-30%]"
          />
          <div
            className="absolute bottom-0 left-0 w-[400px] h-[400px] rounded-full pointer-events-none bg-[radial-gradient(circle,rgba(190,234,209,0.06)_0%,transparent_70%)] translate-x-[-30%] translate-y-[30%]"
          />

          <div className="relative z-10 flex flex-col lg:flex-row items-start lg:items-center justify-between gap-12">
            {/* Left — copy */}
            <div className="lg:max-w-[55%]">
              {/* Trust badge */}
              <div
                className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-bold uppercase tracking-widest mb-8 bg-brand-viridian/20 text-sidebar-accent-foreground border border-brand-viridian/30"
              >
                <CheckCircle2 className="w-3.5 h-3.5" />
                Verify before you pay
              </div>

              <h2
                className="text-4xl md:text-5xl font-extrabold editorial-spacing font-display leading-[1.1] text-white mb-6"
              >
                You&apos;ve worked too hard{" "}
                <span className="text-sidebar-accent-foreground">to risk it on hearsay.</span>
              </h2>

              <p className="text-lg leading-relaxed mb-10 text-white/70 max-w-lg">
                Get started in under five minutes. Your Verification ID is assigned the moment you 
                submit — and our team gets to work.
              </p>

              {/* Disclaimer */}
              <div
                className="text-xs leading-relaxed mb-10 px-4 py-3 rounded-xl bg-white/6 text-white/50 border border-white/8"
              >
                We reduce uncertainty. We do not eliminate it. Reports represent professional
                opinions at the time of verification — not legal guarantees.
              </div>

              {/* CTAs */}
              <div className="flex flex-col sm:flex-row gap-4">
                <Link
                  href={CTA_VERIFY_HREF}
                  className="group inline-flex items-center justify-center gap-2.5 px-10 py-4 rounded-xl font-bold text-base transition-all duration-200 hover:opacity-90 hover:scale-[0.98] bg-brand-viridian text-white shadow-[0_8px_24px_-4px_rgba(63,102,83,0.5)]"
                >
                  Verify a Property Now
                  <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
                </Link>
                <Link
                  href={CTA_AGENT_HREF}
                  className="inline-flex items-center justify-center gap-2 px-10 py-4 rounded-xl font-bold text-base transition-all duration-200 hover:bg-white/10 text-white border border-white/20"
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
                  className="flex items-start gap-4 p-5 rounded-2xl bg-white/6 border border-white/8"
                >
                  <div
                    className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 bg-brand-viridian/25"
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
