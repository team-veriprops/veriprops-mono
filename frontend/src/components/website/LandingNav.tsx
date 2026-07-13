"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Menu, X } from "lucide-react";
import { navLinks, CTA_VERIFY_HREF } from "./home.data";
import { useAuthStore } from "@components/website/auth/libs/useAuthStore";
import { UserType, UserPersona } from "@components/website/auth/models";
import { ROUTES } from "@lib/routes";
import BrandLogo from "../ui/BrandLogo";
import { cn } from "@lib/utils";

export default function LandingNav() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  const session = useAuthStore((s) => s.session);
  const user = session?.user;
  const isLoggedIn = !!session;
  const dashboardHref =
    user?.userType === UserType.ADMIN
      ? ROUTES.ADMIN.DASHBOARD
      : user?.personas?.includes(UserPersona.AGENT)
        ? ROUTES.AGENT.DASHBOARD
        : ROUTES.PORTAL.DASHBOARD;

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 12);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <nav
      className={cn(
        "fixed top-0 inset-x-0 z-50 transition-all duration-300 border-b",
        scrolled
          ? "bg-white/92 backdrop-blur-xl border-brand-outline-variant/15 shadow-[0_2px_16px_rgba(0,13,34,0.06)]"
          : "bg-white/0 border-transparent shadow-none"
      )}
    >
      <div className="max-w-7xl mx-auto px-6 lg:px-8 h-18 flex items-center justify-between py-4">
        <BrandLogo />

        {/* Desktop nav links */}
        <div className="hidden md:flex items-center gap-8">
          {navLinks.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors duration-150"
            >
              {link.label}
            </a>
          ))}
        </div>

        {/* Desktop CTAs */}
        <div className="hidden md:flex items-center gap-3">
          {isLoggedIn ? (
            <>
              <Link
                href={CTA_VERIFY_HREF}
                className="px-5 py-2.5 text-sm font-semibold rounded-lg transition-all duration-150 hover:bg-gray-50 text-brand-navy"
              >
                Verify a Property
              </Link>
              <Link
                href={dashboardHref}
                className="signature-gradient text-white px-6 py-2.5 rounded-lg text-sm font-semibold transition-all duration-200 hover:opacity-90 hover:scale-[0.98] active:scale-95 shadow-[0_4px_14px_-3px_rgba(0,13,34,0.35)]"
              >
                Back to Dashboard
              </Link>
            </>
          ) : (
            <>
              <Link
                href={ROUTES.AUTH.LOGIN}
                className="px-5 py-2.5 text-sm font-semibold rounded-lg transition-all duration-150 hover:bg-gray-50 text-brand-navy"
              >
                Log in
              </Link>
              <Link
                href={CTA_VERIFY_HREF}
                className="signature-gradient text-white px-6 py-2.5 rounded-lg text-sm font-semibold transition-all duration-200 hover:opacity-90 hover:scale-[0.98] active:scale-95 shadow-[0_4px_14px_-3px_rgba(0,13,34,0.35)]"
              >
                Verify a Property
              </Link>
            </>
          )}
        </div>

        {/* Mobile hamburger */}
        <button
          className="md:hidden p-2 rounded-lg transition-colors text-brand-navy"
          onClick={() => setMenuOpen(!menuOpen)}
          aria-label={menuOpen ? "Close menu" : "Open menu"}
        >
          {menuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </div>

      {/* Mobile menu overlay */}
      {menuOpen && (
        <div
          className="md:hidden absolute inset-x-0 top-full bg-white/98 backdrop-blur-xl border-t border-brand-outline-variant/15"
        >
          <div className="max-w-7xl mx-auto px-6 py-6 flex flex-col gap-1">
            {navLinks.map((link) => (
              <a
                key={link.href}
                href={link.href}
                onClick={() => setMenuOpen(false)}
                className="py-3 px-4 text-base font-medium rounded-lg transition-colors hover:bg-gray-50 text-brand-on-surface"
              >
                {link.label}
              </a>
            ))}
            <div className="mt-4 pt-4 flex flex-col gap-3 border-t border-brand-outline-variant/30">
              {isLoggedIn ? (
                <>
                  <Link
                    href={CTA_VERIFY_HREF}
                    onClick={() => setMenuOpen(false)}
                    className="py-3 px-4 text-center text-sm font-semibold rounded-lg border transition-colors text-brand-navy border-brand-outline-variant/40"
                  >
                    Verify a Property
                  </Link>
                  <Link
                    href={dashboardHref}
                    onClick={() => setMenuOpen(false)}
                    className="signature-gradient text-white py-3 px-4 text-center text-sm font-semibold rounded-lg"
                  >
                    Back to Dashboard
                  </Link>
                </>
              ) : (
                <>
                  <Link
                    href={ROUTES.AUTH.LOGIN}
                    onClick={() => setMenuOpen(false)}
                    className="py-3 px-4 text-center text-sm font-semibold rounded-lg border transition-colors text-brand-navy border-brand-outline-variant/40"
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
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </nav>
  );
}
