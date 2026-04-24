"use client";

import { useState } from "react";
import Link from "next/link";
import { CheckCircle2, ArrowRight } from "lucide-react";
import { footerLinks } from "./home.data";

export default function LandingFooter() {
  const [email, setEmail] = useState("");

  return (
    <footer
      style={{ backgroundColor: "var(--brand-surface-low)", borderTop: "1px solid rgba(196,198,207,0.2)" }}
    >
      <div className="max-w-7xl mx-auto px-6 lg:px-8 pt-16 pb-10">
        {/* Main grid */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-12 mb-16">
          {/* Brand column */}
          <div className="md:col-span-1">
            {/* Logo */}
            <Link href="/" className="inline-flex items-center gap-2.5 mb-5">
              <div
                className="w-8 h-8 rounded-lg flex items-center justify-center signature-gradient"
              >
                <CheckCircle2 className="w-4 h-4 text-white" strokeWidth={2.5} />
              </div>
              <span
                className="text-lg font-extrabold font-display editorial-spacing"
                style={{ color: "var(--brand-navy)" }}
              >
                Veriprops
              </span>
            </Link>

            <p
              className="text-sm leading-relaxed mb-6"
              style={{ color: "var(--brand-on-surface-variant)" }}
            >
              The Sovereign Curator of Real Estate Verification. We reduce
              uncertainty. We do not eliminate it.
            </p>

            {/* Socials */}
            <div className="flex items-center gap-3">
              {footerLinks.socials.map((social) => (
                <a
                  key={social.label}
                  href={social.href}
                  aria-label={social.label}
                  className="w-9 h-9 rounded-lg flex items-center justify-center transition-colors duration-150 hover:bg-gray-100 text-xs font-bold"
                  style={{
                    color: "var(--brand-on-surface-variant)",
                    border: "1px solid rgba(196,198,207,0.3)",
                  }}
                >
                  {social.label.slice(0, 2)}
                </a>
              ))}
            </div>
          </div>

          {/* Resources column */}
          <div>
            <h4
              className="text-xs font-bold uppercase tracking-widest mb-5"
              style={{ color: "var(--brand-navy)" }}
            >
              Resources
            </h4>
            <ul className="space-y-3">
              {footerLinks.resources.map((link) => (
                <li key={link.label}>
                  <a
                    href={link.href}
                    className="text-sm transition-colors duration-150 hover:underline"
                    style={{ color: "var(--brand-on-surface-variant)" }}
                    onMouseEnter={(e) =>
                      ((e.target as HTMLElement).style.color = "var(--brand-navy)")
                    }
                    onMouseLeave={(e) =>
                      ((e.target as HTMLElement).style.color = "var(--brand-on-surface-variant)")
                    }
                  >
                    {link.label}
                  </a>
                </li>
              ))}
            </ul>
          </div>

          {/* Company column */}
          <div>
            <h4
              className="text-xs font-bold uppercase tracking-widest mb-5"
              style={{ color: "var(--brand-navy)" }}
            >
              Company
            </h4>
            <ul className="space-y-3">
              {footerLinks.company.map((link) => (
                <li key={link.label}>
                  <Link
                    href={link.href}
                    className="text-sm transition-colors duration-150 hover:underline"
                    style={{ color: "var(--brand-on-surface-variant)" }}
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Newsletter column */}
          <div>
            <h4
              className="text-xs font-bold uppercase tracking-widest mb-5"
              style={{ color: "var(--brand-navy)" }}
            >
              Stay Certified
            </h4>
            <p
              className="text-sm leading-relaxed mb-4"
              style={{ color: "var(--brand-on-surface-variant)" }}
            >
              Get updates on market insights, new features, and diaspora property trends.
            </p>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                setEmail("");
              }}
              className="flex gap-2"
            >
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Email address"
                className="flex-1 px-4 py-2.5 text-sm rounded-lg outline-none transition-all"
                style={{
                  backgroundColor: "#fff",
                  border: "1px solid rgba(196,198,207,0.3)",
                  color: "var(--brand-on-surface)",
                }}
                required
              />
              <button
                type="submit"
                className="flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center signature-gradient transition-opacity hover:opacity-90"
              >
                <ArrowRight className="w-4 h-4 text-white" />
              </button>
            </form>
          </div>
        </div>

        {/* Bottom bar */}
        <div
          className="flex flex-col md:flex-row items-center justify-between gap-4 pt-8"
          style={{ borderTop: "1px solid rgba(196,198,207,0.25)" }}
        >
          <p className="text-xs" style={{ color: "var(--brand-on-surface-variant)" }}>
            © 2025 Veriprops. Jurisdiction: Nigeria. All communications are recorded for
            quality and security.
          </p>
          <p
            className="text-xs italic"
            style={{ color: "rgba(68,71,78,0.6)" }}
          >
            &ldquo;We reduce uncertainty. We do not eliminate it.&rdquo;
          </p>
        </div>
      </div>
    </footer>
  );
}
