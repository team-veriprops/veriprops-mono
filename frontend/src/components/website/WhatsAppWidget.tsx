"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";

import { usePublicConfigQuery } from "@components/website/auth/libs/useAuthQueries";
import { cn } from "@lib/utils";
import { isPaymentFlowPath, pageCodeFor, waMeUrl } from "@lib/whatsapp";

/**
 * Floating WhatsApp entry point (PRD §26.4.1).
 *
 * WhatsApp is the conversational front door; this button is the door handle. It rides on
 * every public and authenticated page **except inside the payment flow**, where a way out
 * costs conversion at the highest-value moment. The button only deep-links — there is no
 * in-page chat UI at v1 — and the prefilled message carries a page code so an enquiry can
 * be attributed to where it started (§26.10).
 *
 * The number comes from `/config/public` and is never hardcoded here: it is the customer's
 * anti-impersonation anchor (§26.1.2), so one backend value feeds the widget, certified
 * reports, and bot copy alike. Until it resolves, the button simply does not render.
 */
export default function WhatsAppWidget() {
  const pathname = usePathname() || "";
  const { data: config } = usePublicConfigQuery();
  // Entrance runs after mount so the button eases in rather than snapping onto a page
  // that is still painting.
  const [entered, setEntered] = useState(false);

  useEffect(() => {
    const frame = requestAnimationFrame(() => setEntered(true));
    return () => cancelAnimationFrame(frame);
  }, []);

  if (!config?.whatsappWidgetEnabled) return null;
  if (isPaymentFlowPath(pathname)) return null;

  const href = waMeUrl(config.whatsappNumber ?? "", pageCodeFor(pathname));
  if (!href) return null;

  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      aria-label="Chat with Veriprops on WhatsApp"
      data-testid="whatsapp-widget"
      className={cn(
        // Fixed placement keeps the button out of document flow — it can appear at any
        // moment without shifting a single pixel of the page (zero CLS).
        "fixed bottom-5 right-5 z-40 flex h-14 w-14 items-center justify-center rounded-full",
        "bg-[#25D366] text-white shadow-lg outline-offset-2",
        "transition-[opacity,transform] duration-300 motion-reduce:transition-none",
        "hover:brightness-95 focus-visible:outline-2 focus-visible:outline-[#25D366]",
        entered ? "translate-y-0 opacity-100" : "translate-y-2 opacity-0",
      )}
    >
      <WhatsAppGlyph />
    </a>
  );
}

/** The official WhatsApp mark, per Meta's brand guidelines (solid glyph, no recolouring). */
function WhatsAppGlyph() {
  return (
    <svg
      viewBox="0 0 24 24"
      className="h-7 w-7"
      fill="currentColor"
      aria-hidden="true"
      focusable="false"
    >
      <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.174.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51l-.57-.01c-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.872.118.571-.085 1.758-.719 2.006-1.413.247-.694.247-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 0 1-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 0 1-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884a9.82 9.82 0 0 1 6.988 2.898 9.83 9.83 0 0 1 2.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.82 11.82 0 0 0 12.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.548 4.142 1.588 5.945L.057 24l6.305-1.654a11.9 11.9 0 0 0 5.688 1.448h.005c6.554 0 11.89-5.335 11.893-11.893A11.82 11.82 0 0 0 20.464 3.488" />
    </svg>
  );
}
