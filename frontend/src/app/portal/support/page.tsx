import Link from "next/link";
import { MessageSquare, HelpCircle } from "lucide-react";
import { ROUTES } from "@lib/routes";

export default function PortalSupportPage() {
  return (
    <div className="p-6 lg:p-8 max-w-2xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-extrabold font-display" style={{ color: "var(--brand-navy)" }}>
          Support
        </h1>
      </div>

      <div
        className="rounded-2xl p-6 mb-4"
        style={{ backgroundColor: "#fff", border: "1px solid rgba(196,198,207,0.15)", boxShadow: "0 2px 8px rgba(0,13,34,0.04)" }}
      >
        <div className="flex items-start gap-4">
          <div
            className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0"
            style={{ backgroundColor: "rgba(63,102,83,0.08)" }}
          >
            <MessageSquare className="w-5 h-5" style={{ color: "var(--brand-viridian)" }} />
          </div>
          <div>
            <h2 className="text-sm font-bold mb-1" style={{ color: "var(--brand-navy)" }}>
              Verification-specific questions
            </h2>
            <p className="text-sm mb-3" style={{ color: "var(--brand-on-surface-variant)" }}>
              For questions about a specific verification — status, report, timeline — use the Messages tab on your verification page. Our team responds within one business day.
            </p>
            <Link
              href={ROUTES.PORTAL.VERIFICATIONS}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-opacity hover:opacity-80"
              style={{ backgroundColor: "rgba(63,102,83,0.08)", color: "var(--brand-viridian)", border: "1px solid rgba(63,102,83,0.2)" }}
            >
              My Verifications →
            </Link>
          </div>
        </div>
      </div>

      <div
        className="rounded-2xl p-6"
        style={{ backgroundColor: "#fff", border: "1px solid rgba(196,198,207,0.15)", boxShadow: "0 2px 8px rgba(0,13,34,0.04)" }}
      >
        <div className="flex items-start gap-4">
          <div
            className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0"
            style={{ backgroundColor: "rgba(0,13,34,0.05)" }}
          >
            <HelpCircle className="w-5 h-5" style={{ color: "var(--brand-on-surface-variant)" }} />
          </div>
          <div>
            <h2 className="text-sm font-bold mb-1" style={{ color: "var(--brand-navy)" }}>
              General enquiries
            </h2>
            <p className="text-sm mb-3" style={{ color: "var(--brand-on-surface-variant)" }}>
              For account, billing, or other questions, email us and we&apos;ll get back to you within 24 hours.
            </p>
            <a
              href="mailto:support@veriprops.com"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-opacity hover:opacity-80"
              style={{ backgroundColor: "rgba(0,13,34,0.05)", color: "var(--brand-navy)", border: "1px solid rgba(196,198,207,0.3)" }}
            >
              support@veriprops.com
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
