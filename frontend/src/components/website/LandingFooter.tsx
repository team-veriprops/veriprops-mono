"use client";

import Link from "next/link";
import { footerLinks, type FooterLink } from "./home.data";
import BrandLogo from "../ui/BrandLogo";
import { cn } from "@lib/utils";

// Tailwind utilities for each platform's brand token (theme.css `--social-*`).
const socialHoverClasses: Record<string, string> = {
  Facebook:  "hover:text-social-facebook hover:border-social-facebook/40 hover:bg-social-facebook/10",
  Twitter:   "hover:text-social-twitter hover:border-social-twitter/40 hover:bg-social-twitter/10",
  LinkedIn:  "hover:text-social-linkedin hover:border-social-linkedin/40 hover:bg-social-linkedin/10",
  Instagram: "hover:text-social-instagram hover:border-social-instagram/40 hover:bg-social-instagram/10",
  YouTube:   "hover:text-social-youtube hover:border-social-youtube/40 hover:bg-social-youtube/10",
};

const socialIcons: Record<string, React.ReactNode> = {
  Facebook: (
    <svg viewBox="0 0 24 24" className="w-4 h-4" fill="currentColor" aria-hidden="true">
      <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z" />
    </svg>
  ),
  Twitter: (
    <svg viewBox="0 0 24 24" className="w-4 h-4" fill="currentColor" aria-hidden="true">
      <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-4.714-6.231-5.401 6.231H2.74l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
    </svg>
  ),
  LinkedIn: (
    <svg viewBox="0 0 24 24" className="w-4 h-4" fill="currentColor" aria-hidden="true">
      <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 0 1-2.063-2.065 2.064 2.064 0 1 1 2.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
    </svg>
  ),
  Instagram: (
    <svg viewBox="0 0 24 24" className="w-4 h-4" fill="currentColor" aria-hidden="true">
      <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838a6.162 6.162 0 1 0 0 12.324 6.162 6.162 0 0 0 0-12.324zM12 16a4 4 0 1 1 0-8 4 4 0 0 1 0 8zm6.406-11.845a1.44 1.44 0 1 0 0 2.881 1.44 1.44 0 0 0 0-2.881z" />
    </svg>
  ),
  YouTube: (
    <svg viewBox="0 0 24 24" className="w-4 h-4" fill="currentColor" aria-hidden="true">
      <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z" />
    </svg>
  ),
};

const linkColumns: { title: string; links: FooterLink[] }[] = [
  { title: "Platform", links: footerLinks.platform },
  { title: "Company", links: footerLinks.company },
  { title: "Legal", links: footerLinks.legal },
];

// Internal app routes use Next <Link>; on-page anchors (#…), mailto:, and external
// URLs use a plain <a>. Same className drives both so every link behaves identically.
function FooterLinkItem({ label, href }: FooterLink) {
  const className = "text-sm transition-colors duration-150 hover:underline text-brand-on-surface-variant hover:text-brand-navy";

  if (href.startsWith("/")) {
    return (
      <Link href={href} className={className}>
        {label}
      </Link>
    );
  }
  return (
    <a href={href} className={className}>
      {label}
    </a>
  );
}

export default function LandingFooter() {
  return (
    <footer
      className="bg-brand-surface-low border-t border-brand-outline-variant/20"
    >
      <div className="max-w-7xl mx-auto px-6 lg:px-8 pt-16 pb-10">
        {/* Main grid */}
        <div className="grid grid-cols-1 md:grid-cols-5 gap-12 mb-16">
          {/* Brand column */}
          <div className="md:col-span-2">
            <BrandLogo />

            <p
              className="text-sm leading-relaxed mb-6 text-brand-on-surface-variant"
            >
              <br />
              
              Helping Nigerians buy property safely; through 
              trusted, independent verification and real 
              due diligence. 

              <br />
              <br />
              <b className="text-xs">Buy with confidence. Verify before you pay.</b>
            </p>

            {/* Socials — a configured handle renders a link; an unset ("#" or empty)
                handle renders a non-interactive icon rather than a dead link. */}
            <div className="flex items-center gap-3">
              {footerLinks.socials.map((social) => {
                const configured = social.href && social.href !== "#";
                const baseClass =
                  "w-9 h-9 rounded-lg flex items-center justify-center transition-all duration-150 text-brand-on-surface-variant border border-brand-outline-variant/30";

                if (!configured) {
                  return (
                    <span
                      key={social.label}
                      aria-label={social.label}
                      aria-disabled="true"
                      className={cn(baseClass, "opacity-50 cursor-default")}
                    >
                      {socialIcons[social.label]}
                    </span>
                  );
                }

                return (
                  <a
                    key={social.label}
                    href={social.href}
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label={social.label}
                    className={cn(baseClass, socialHoverClasses[social.label])}
                  >
                    {socialIcons[social.label]}
                  </a>
                );
              })}
            </div>
          </div>

          {/* Link columns — Platform, Company, Legal */}
          {linkColumns.map((column) => (
            <div key={column.title}>
              <h4
                className="text-xs font-bold uppercase tracking-widest mb-5 text-brand-navy"
              >
                {column.title}
              </h4>
              <ul className="space-y-3">
                {column.links.map((link) => (
                  <li key={link.label}>
                    <FooterLinkItem {...link} />
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {/* Bottom bar */}
        <div
          className="flex flex-col md:flex-row items-center justify-between gap-4 pt-8 border-t border-brand-outline-variant/25"
        >
          <p className="text-xs text-brand-on-surface-variant">
            © {new Date().getFullYear()} Veriprops. Jurisdiction: Nigeria. All communications
            are recorded for quality and security.
          </p>
          <p
            className="text-xs italic text-brand-on-surface-variant/60"
          >
            &ldquo;We reduce uncertainty. We do not eliminate it.&rdquo;
          </p>
        </div>
      </div>
    </footer>
  );
}
