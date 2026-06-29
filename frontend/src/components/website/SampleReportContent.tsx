import Link from "next/link";
import { ShieldCheck, MapPin, FileText, Scale, Lock, ArrowRight } from "lucide-react";
import { CTA_VERIFY_HREF } from "./home.data";

/**
 * Static, redacted preview of a Veriprops certified report — so a prospective
 * buyer can see exactly what they receive before paying. Representative content
 * only; the live report (Phase 10) is generated from real verification data.
 */
const sections = [
  {
    icon: FileText,
    title: "Registry & Title",
    findings: [
      "Certificate of Occupancy confirmed at the Lagos State Land Registry.",
      "Ownership chain traced through two prior transfers — no breaks.",
      "Registered title holder matches the seller's submitted identity.",
    ],
  },
  {
    icon: MapPin,
    title: "Physical Findings",
    findings: [
      "On-site inspection completed; GPS-stamped photographs captured.",
      "Property matches the submitted address and landmark description.",
      "Occupancy: vacant land, fenced, no visible encroachment.",
    ],
  },
  {
    icon: ShieldCheck,
    title: "Boundary & Survey",
    findings: [
      "Boundary survey reconciled against the registered survey plan.",
      "Measured land size within tolerance of the documented size.",
      "Beacon coordinates recorded and mapped.",
    ],
  },
  {
    icon: Scale,
    title: "Legal Opinion (Premium)",
    findings: [
      "Signed by an NBA-licensed lawyer — opinion owned by the lawyer, transmitted by Veriprops.",
      "No encumbrances, liens, or pending litigation identified on search.",
      "Recommendation: proceed with standard contractual safeguards.",
    ],
  },
];

export default function SampleReportContent() {
  return (
    <section className="py-16 md:py-24">
      <div className="max-w-4xl mx-auto px-6 lg:px-8">
        {/* Heading */}
        <div className="text-center mb-12">
          <p
            className="text-xs font-bold uppercase tracking-widest mb-3"
            style={{ color: "var(--brand-viridian)" }}
          >
            Sample Certified Report
          </p>
          <h1
            className="editorial-spacing text-3xl md:text-4xl font-bold"
            style={{ color: "var(--brand-navy)", fontFamily: "var(--font-display)" }}
          >
            See exactly what you receive
          </h1>
          <p className="mt-4 text-sm md:text-base" style={{ color: "var(--brand-on-surface-variant)" }}>
            A representative, redacted example. Every real report carries a Trust Score,
            a public Verification ID, and a legal footer on every page.
          </p>
        </div>

        {/* Report card */}
        <div
          className="rounded-2xl overflow-hidden"
          style={{ backgroundColor: "var(--brand-surface-card)", boxShadow: "0 12px 40px -12px rgba(0,13,34,0.18)" }}
        >
          {/* Report header */}
          <div className="signature-gradient text-white px-8 py-7 flex flex-wrap items-center justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-widest opacity-80">Verification ID</p>
              <p className="text-lg font-bold font-mono">VP-2026-0X4F9A</p>
            </div>
            <div className="text-right">
              <p className="text-xs uppercase tracking-widest opacity-80">Trust Score</p>
              <p className="text-3xl font-bold">92<span className="text-base font-normal opacity-70">/100</span></p>
            </div>
          </div>

          {/* Redacted property line */}
          <div className="px-8 py-5 flex items-center gap-2 text-sm" style={{ color: "var(--brand-on-surface-variant)", borderBottom: "1px solid rgba(196,198,207,0.25)" }}>
            <Lock className="w-4 h-4" aria-hidden="true" />
            Property: Plot 1▮, ▮▮▮▮▮ Crescent, Lekki Phase 1, Lagos
            <span className="ml-1 text-xs italic">(redacted in sample)</span>
          </div>

          {/* Sections */}
          <div className="divide-y" style={{ borderColor: "rgba(196,198,207,0.25)" }}>
            {sections.map(({ icon: Icon, title, findings }) => (
              <div key={title} className="px-8 py-6">
                <div className="flex items-center gap-3 mb-3">
                  <span
                    className="w-9 h-9 rounded-lg flex items-center justify-center"
                    style={{ backgroundColor: "var(--brand-viridian-xlight)", color: "var(--brand-viridian)" }}
                  >
                    <Icon className="w-5 h-5" aria-hidden="true" />
                  </span>
                  <h2 className="text-base font-bold" style={{ color: "var(--brand-navy)" }}>
                    {title}
                  </h2>
                </div>
                <ul className="list-disc pl-5 space-y-1.5 text-sm leading-relaxed" style={{ color: "var(--brand-on-surface-variant)" }}>
                  {findings.map((f) => (
                    <li key={f}>{f}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>

          {/* Legal footer */}
          <p className="px-8 py-5 text-xs italic" style={{ backgroundColor: "var(--brand-surface-low)", color: "rgba(68,71,78,0.7)" }}>
            This report represents a professional opinion, not a legal guarantee. Findings are
            based on information available at the time of verification. Veriprops — Jurisdiction:
            Nigeria. &ldquo;We reduce uncertainty. We do not eliminate it.&rdquo;
          </p>
        </div>

        {/* CTA */}
        <div className="text-center mt-12">
          <Link
            href={CTA_VERIFY_HREF}
            className="group inline-flex items-center justify-center gap-2.5 signature-gradient text-white px-8 py-4 rounded-xl text-base font-bold transition-all duration-200 hover:opacity-90"
          >
            Verify a Property
            <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
          </Link>
        </div>
      </div>
    </section>
  );
}
