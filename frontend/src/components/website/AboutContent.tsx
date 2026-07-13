import type { ReactNode } from "react";
import { cn } from "@lib/utils";

/**
 * About page narrative — adapted from the supplied reference into the Veriprops
 * design system (brand tokens + the home page's section idioms). Pure static
 * server component; the page reuses LandingNav / LandingFooter / CTASection
 * around it. Copy is held in `{"…"}` expressions so apostrophes/quotes don't
 * trip react/no-unescaped-entities.
 */

function Eyebrow({
  children,
  tone = "light",
}: {
  children: ReactNode;
  tone?: "light" | "dark";
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-widest",
        tone === "dark"
          ? "bg-brand-viridian/20 text-sidebar-accent-foreground border border-brand-viridian/30"
          : "bg-brand-viridian/8 text-brand-viridian border border-brand-viridian/15"
      )}
    >
      {children}
    </span>
  );
}

const values = [
  {
    title: "Honesty over hype",
    body:
      "We tell you what we found and what we couldn't confirm. We'd rather lose a sale than oversell a certainty we can't stand behind. Our credibility is the only thing we can't afford to lose.",
  },
  {
    title: "Proof over promises",
    body:
      "Anyone can call a property genuine. We show the registry search, the boundary survey, the GPS-stamped photos, and the signatures of the people who did the work. Evidence, not assurances.",
  },
  {
    title: "People over distance",
    body:
      "Being thousands of miles away shouldn't put you at a disadvantage. We stand on the ground so you don't have to — and we treat your money and your trust as if they were our own.",
  },
];

const stats = [
  { value: "2,400+", label: "Properties verified" },
  { value: "98%", label: "Report accuracy rate" },
  { value: "£4.1M+", label: "Buyer funds protected" },
  { value: "1 in 6", label: "Listings flagged with an issue" },
];

export default function AboutContent() {
  return (
    <>
      {/* ── Hero ── */}
      <section
        className="relative pt-32 lg:pt-40 pb-20 lg:pb-24 overflow-hidden bg-brand-surface-card"
      >
        {/* Warm ambient glow */}
        <div
          className="absolute top-24 left-1/2 -translate-x-1/2 w-[680px] h-[540px] max-w-[90%] pointer-events-none bg-[radial-gradient(circle,rgba(63,102,83,0.08),transparent_68%)]"
        />
        <div className="relative z-10 max-w-3xl mx-auto px-6 lg:px-8 text-center animate-fade-up">
          <div className="mb-7">
            <Eyebrow>About Veriprops</Eyebrow>
          </div>
          <h1
            className="text-4xl md:text-5xl lg:text-6xl font-extrabold editorial-spacing font-display leading-[1.08] mb-6 text-brand-navy"
          >
            {"We help Nigerians buy property at home — "}
            <em className="text-brand-viridian">without the fear.</em>
          </h1>
          <p
            className="text-lg md:text-xl leading-relaxed max-w-2xl mx-auto text-brand-on-surface-variant"
          >
            {"Whether you're across the city or across an ocean, you deserve to know exactly what you're buying before you part with a single naira. That certainty is the whole reason we exist."}
          </p>
        </div>
      </section>

      {/* ── The principle (dark) ── */}
      <section className="relative py-20 lg:py-24 overflow-hidden dark-section-gradient">
        <div
          className="absolute -top-24 -right-16 w-[320px] h-[320px] rounded-full pointer-events-none bg-[radial-gradient(circle,rgba(63,102,83,0.16),transparent_70%)]"
        />
        <div className="relative z-10 max-w-4xl mx-auto px-6 lg:px-8 text-center">
          <p className="text-3xl md:text-4xl lg:text-5xl font-display editorial-spacing leading-[1.2] text-white">
            {"We reduce uncertainty."}
            <br />
            {"We do "}
            <em className="text-sidebar-accent-foreground">not</em>
            {" eliminate it."}
          </p>
          <p className="mt-6 text-base md:text-lg leading-relaxed max-w-2xl mx-auto text-white/70">
            {"Anyone can promise you a guarantee. We'd rather tell you the truth: real diligence has edges, and we show you ours. That honesty is the foundation everything else here is built on."}
          </p>
        </div>
      </section>

      {/* ── Origin story ── */}
      <section className="py-24 lg:py-28 bg-brand-surface-low">
        <div className="max-w-3xl mx-auto px-6 lg:px-8">
          <Eyebrow>Why we exist</Eyebrow>
          <h2
            className="mt-5 text-3xl md:text-4xl lg:text-5xl font-extrabold editorial-spacing font-display leading-tight mb-8 text-brand-navy"
          >
            It started with a deposit that vanished.
          </h2>
          <div className="space-y-6 text-lg leading-relaxed text-brand-on-surface-variant">
            <p>
              {"A friend of ours wired the deposit for a plot of land in Lekki from his flat in London. He'd seen the photos. He'd spoken to an agent who sounded sure of everything. He'd even sent a cousin to walk the land."}
            </p>
            <p
              className="text-2xl md:text-3xl font-display editorial-spacing leading-[1.35] py-2 text-brand-navy"
            >
              {"By the time he flew home, he learned the same plot had already been "}
              <span className="relative inline-block">
                sold to four other people
                <span
                  className="absolute -bottom-1 left-0 right-0 h-0.75 rounded-full bg-brand-viridian/40"
                />
              </span>
              {"."}
            </p>
            <p>
              {"His money was gone. So was the future he'd been planning for years. And the hardest part wasn't the fraud itself — it was discovering how ordinary his story was. Ask almost any Nigerian living abroad and they know someone it happened to. A trusted relative. A confident agent. A beautiful listing. And no real way to know what was true until it was far too late."}
            </p>
            <p>
              {"We built "}
              <strong className="text-brand-navy">Veriprops</strong>
              {" because distance should never mean blind trust. Buying property back home should feel like building something — not gambling on it. So we put qualified people on the ground to check what a photo never can: who really owns it, where the boundaries actually fall, whether anyone else has a claim, and whether the document in your hand means what it says."}
            </p>
            <p>
              {"One verification at a time, we're making sure the next person doesn't lose a deposit — or a dream — to something that was never anyone's to sell."}
            </p>
          </div>
        </div>
      </section>

      {/* ── What we do ── */}
      <section className="py-24 lg:py-28 bg-brand-surface-card">
        <div className="max-w-3xl mx-auto px-6 lg:px-8">
          <Eyebrow>What we do</Eyebrow>
          <h2
            className="mt-5 text-3xl md:text-4xl lg:text-5xl font-extrabold editorial-spacing font-display leading-tight mb-8 text-brand-navy"
          >
            {`We turn "I think it's genuine" into "I know it is."`}
          </h2>
          <div className="space-y-6 text-lg leading-relaxed text-brand-on-surface-variant">
            <p>
              {"Veriprops is a property verification platform built for the way Nigerians actually buy — often remotely, often on trust, often with everything on the line. You bring us a property, whether you found it online or were shown it in person, and we do the work most buyers can't do for themselves from afar."}
            </p>
            <p>
              {"Our certified agents — surveyors, registry specialists, and lawyers — combine official record checks with a physical inspection of the property itself. We confirm ownership, map the boundaries, and surface any encumbrance: a lien, a caveat, pending litigation, a competing claim. Then we translate all of it into something you can actually act on."}
            </p>
            <p>
              {"Every verified property comes back with three things: a "}
              <strong className="text-brand-navy">Trust Score</strong>
              {" from 0 to 100 that tells you plainly where you stand, a public "}
              <strong className="text-brand-navy">Verification ID</strong>
              {" you can share with family or a bank, and a signed "}
              <strong className="text-brand-navy">certified report</strong>
              {" detailed enough to support real financing decisions. No jargon. No guesswork. Just the truth about what you're considering — before your money moves."}
            </p>
          </div>
        </div>
      </section>

      {/* ── Values ── */}
      <section className="py-24 lg:py-28 bg-brand-surface-low">
        <div className="max-w-7xl mx-auto px-6 lg:px-8">
          <div className="text-center max-w-2xl mx-auto mb-14">
            <div className="mb-5">
              <Eyebrow>What we stand for</Eyebrow>
            </div>
            <h2
              className="text-3xl md:text-4xl lg:text-5xl font-extrabold editorial-spacing font-display leading-tight text-brand-navy"
            >
              Three commitments we don&rsquo;t bend on.
            </h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {values.map((value, i) => (
              <div
                key={value.title}
                className="landing-card rounded-2xl p-8 bg-brand-surface-card border border-brand-outline-variant/30"
              >
                <div
                  className="w-12 h-12 rounded-xl flex items-center justify-center mb-5 font-display font-bold text-lg bg-brand-viridian/8 text-brand-viridian"
                >
                  {String(i + 1).padStart(2, "0")}
                </div>
                <h3 className="text-xl font-bold font-display mb-3 text-brand-navy">
                  {value.title}
                </h3>
                <p className="text-sm leading-relaxed text-brand-on-surface-variant">
                  {value.body}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Vision (dark split) ── */}
      <section className="relative py-24 lg:py-28 overflow-hidden dark-section-gradient">
        <div
          className="absolute -bottom-32 -left-20 w-[420px] h-[420px] rounded-full pointer-events-none bg-[radial-gradient(circle,rgba(63,102,83,0.14),transparent_70%)]"
        />
        <div className="relative z-10 max-w-7xl mx-auto px-6 lg:px-8 grid grid-cols-1 lg:grid-cols-[0.9fr_1.1fr] gap-12 lg:gap-14 items-center">
          <div>
            <Eyebrow tone="dark">Where we&rsquo;re going</Eyebrow>
            <h2 className="mt-5 text-3xl md:text-4xl lg:text-5xl font-extrabold editorial-spacing font-display leading-[1.1] text-white">
              A real estate market built on verified truth.
            </h2>
          </div>
          <div className="space-y-5 text-lg leading-relaxed text-white/75">
            <p>
              {"Today, too much of property in Nigeria runs on hearsay — on who you know and who you're willing to believe. We think that's backwards. We envision a market where every serious transaction starts from verified information, where a Verification ID is as expected as a price, and where trust is something you can check rather than simply hope for."}
            </p>
            <p>
              {"We're early, and we won't pretend otherwise. But every property we verify makes the market a little safer, a little clearer, and a little harder to exploit — for buyers and renters here at home and for the millions building toward a return from abroad."}
            </p>
          </div>
        </div>
      </section>

      {/* ── Stats ── */}
      <section className="py-24 lg:py-28 bg-brand-surface-card">
        <div className="max-w-5xl mx-auto px-6 lg:px-8">
          <div className="text-center max-w-2xl mx-auto mb-12">
            <div className="mb-5">
              <Eyebrow>Where we stand today</Eyebrow>
            </div>
            <h2
              className="text-3xl md:text-4xl lg:text-5xl font-extrabold editorial-spacing font-display leading-tight text-brand-navy"
            >
              The work, in numbers.
            </h2>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {stats.map((stat) => (
              <div
                key={stat.label}
                className="landing-card rounded-2xl p-6 text-center bg-brand-surface-card border border-brand-outline-variant/30"
              >
                <div
                  className="text-3xl md:text-4xl font-display font-bold editorial-spacing text-brand-viridian"
                >
                  {stat.value}
                </div>
                <div className="mt-2 text-sm text-brand-on-surface-variant">
                  {stat.label}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>
    </>
  );
}
