export default function WhyWeExist() {
  return (
    <section
      id="why-we-exist"
      className="relative pt-24 lg:pt-32 pb-16 lg:pb-20 overflow-hidden"
      style={{ backgroundColor: "var(--brand-surface-low)" }}
    >
      {/* Subtle background grid — distinguishes this section from the plain ecosystem section below */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          backgroundImage:
            "radial-gradient(circle at 1px 1px, rgba(0,13,34,0.04) 1px, transparent 0)",
          backgroundSize: "40px 40px",
        }}
      />

      <div className="relative z-10 max-w-7xl mx-auto px-6 lg:px-8">
        <div className="max-w-3xl">
          {/* Eyebrow */}
          <div
            className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-widest mb-8"
            style={{
              backgroundColor: "rgba(63,102,83,0.08)",
              color: "var(--brand-viridian)",
              border: "1px solid rgba(63,102,83,0.15)",
            }}
          >
            Why we exist
          </div>

          {/* Opening anecdote — lead emphasis */}
          <p
            className="text-2xl md:text-3xl font-display editorial-spacing leading-[1.35] mb-8"
            style={{ color: "var(--brand-navy)" }}
          >
            A friend wired the deposit for a plot in Lekki from London. By the
            time he flew home, he learned the same land had been{" "}
            <span className="relative inline-block">
              sold to four other people
              <span
                className="absolute -bottom-1 left-0 right-0 h-[3px] rounded-full"
                style={{ background: "var(--brand-viridian)", opacity: 0.4 }}
              />
            </span>
            .
          </p>

          {/* Body */}
          <div
            className="space-y-6 text-lg leading-relaxed"
            style={{ color: "var(--brand-on-surface-variant)" }}
          >
            <p>
              That story isn&rsquo;t rare &mdash; it&rsquo;s the norm. For
              Nigerians building a life abroad, sending money home should feel
              like progress, not a gamble. Too often it&rsquo;s the opposite: a
              trusted relative, a confident agent, a beautiful listing, and no
              way to know what&rsquo;s real until it&rsquo;s too late.
            </p>
            <p>
              We started Veriprops because distance shouldn&rsquo;t mean blind
              trust. We put qualified people on the ground &mdash; surveyors,
              registry agents, lawyers &mdash; to check what a photo can&rsquo;t.
              So the next person doesn&rsquo;t lose a deposit, or a dream, to
              something that was never theirs to sell.
            </p>
          </div>

          {/* Signature */}
          <p
            className="mt-10 text-base font-semibold font-display editorial-spacing"
            style={{ color: "var(--brand-viridian)" }}
          >
            &mdash; The Veriprops team, Lagos &amp; London
          </p>
        </div>
      </div>
    </section>
  );
}
