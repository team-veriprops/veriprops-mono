"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Menu, X, CheckCircle2 } from "lucide-react";
import { navLinks, CTA_VERIFY_HREF } from "./home.data";

export default function LandingNav() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 12);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <nav
      className="fixed top-0 inset-x-0 z-50 transition-all duration-300"
      style={{
        backgroundColor: scrolled ? "rgba(255,255,255,0.92)" : "rgba(255,255,255,0)",
        backdropFilter: scrolled ? "blur(20px)" : "none",
        borderBottom: scrolled ? "1px solid rgba(196,198,207,0.15)" : "1px solid transparent",
        boxShadow: scrolled ? "0 2px 16px rgba(0,13,34,0.06)" : "none",
      }}
    >
      <div className="max-w-7xl mx-auto px-6 lg:px-8 h-18 flex items-center justify-between py-4">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2.5 group">
          <div
            className="w-8 h-8 rounded-lg flex items-center justify-center signature-gradient"
          >
            <CheckCircle2 className="w-4.5 h-4.5 text-white" strokeWidth={2.5} />
          </div>
          <span
            className="text-xl font-extrabold tracking-tight font-display editorial-spacing"
            style={{ color: "var(--brand-navy)" }}
          >
            Veriprops
          </span>
        </Link>

        {/* Desktop nav links */}
        <div className="hidden md:flex items-center gap-8">
          {navLinks.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="text-sm font-medium transition-colors duration-150"
              style={{ color: "var(--brand-on-surface-variant)" }}
              onMouseEnter={(e) =>
                ((e.target as HTMLElement).style.color = "var(--brand-navy)")
              }
              onMouseLeave={(e) =>
                ((e.target as HTMLElement).style.color =
                  "var(--brand-on-surface-variant)")
              }
            >
              {link.label}
            </a>
          ))}
        </div>

        {/* Desktop CTAs */}
        <div className="hidden md:flex items-center gap-3">
          <Link
            href="/auth/login"
            className="px-5 py-2.5 text-sm font-semibold rounded-lg transition-all duration-150 hover:bg-gray-50"
            style={{ color: "var(--brand-navy)" }}
          >
            Log in
          </Link>
          <Link
            href={CTA_VERIFY_HREF}
            className="signature-gradient text-white px-6 py-2.5 rounded-lg text-sm font-semibold transition-all duration-200 hover:opacity-90 hover:scale-[0.98] active:scale-95"
            style={{ boxShadow: "0 4px 14px -3px rgba(0,13,34,0.35)" }}
          >
            Verify a Property
          </Link>
        </div>

        {/* Mobile hamburger */}
        <button
          className="md:hidden p-2 rounded-lg transition-colors"
          style={{ color: "var(--brand-navy)" }}
          onClick={() => setMenuOpen(!menuOpen)}
          aria-label={menuOpen ? "Close menu" : "Open menu"}
        >
          {menuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </div>

      {/* Mobile menu overlay */}
      {menuOpen && (
        <div
          className="md:hidden absolute inset-x-0 top-full"
          style={{
            backgroundColor: "rgba(255,255,255,0.98)",
            backdropFilter: "blur(20px)",
            borderTop: "1px solid rgba(196,198,207,0.15)",
          }}
        >
          <div className="max-w-7xl mx-auto px-6 py-6 flex flex-col gap-1">
            {navLinks.map((link) => (
              <a
                key={link.href}
                href={link.href}
                onClick={() => setMenuOpen(false)}
                className="py-3 px-4 text-base font-medium rounded-lg transition-colors hover:bg-gray-50"
                style={{ color: "var(--brand-on-surface)" }}
              >
                {link.label}
              </a>
            ))}
            <div className="mt-4 pt-4 flex flex-col gap-3" style={{ borderTop: "1px solid rgba(196,198,207,0.3)" }}>
              <Link
                href="/auth/login"
                onClick={() => setMenuOpen(false)}
                className="py-3 px-4 text-center text-sm font-semibold rounded-lg border transition-colors"
                style={{ color: "var(--brand-navy)", borderColor: "rgba(196,198,207,0.4)" }}
              >
                Log in
              </Link>
              <Link
                href={CTA_VERIFY_HREF}
                onClick={() => setMenuOpen(false)}
                className="signature-gradient text-white py-3 px-4 text-center text-sm font-semibold rounded-lg"
              >
                Verify a Property
              </Link>
            </div>
          </div>
        </div>
      )}
    </nav>
  );
}
