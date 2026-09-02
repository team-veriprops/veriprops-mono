"use client";

import { MessageCircle } from "lucide-react";

import { usePublicConfigQuery } from "@components/website/auth/libs/useAuthQueries";
import { pageCodeFor, waContinueUrl } from "@lib/whatsapp";
import { cn } from "@lib/utils";
import { usePathname } from "next/navigation";

/**
 * "Continue this on WhatsApp" (PRD §7.4.3, D58) — the web→chat half of continuation.
 *
 * The channel is only genuinely two-way if a customer can move *to* it as easily as they
 * arrived from it. The link pre-fills the case reference, which the bot matches on the
 * customer's literal words, so this lands on the right case in one tap.
 *
 * Renders **nothing** without a configured number: the official number is the customer's
 * anti-impersonation anchor (§7.1.2), so there is deliberately no hardcoded fallback here
 * or anywhere else.
 */
export default function WhatsAppContinueButton({
  vid,
  className,
}: {
  vid: string;
  className?: string;
}) {
  const { data: publicConfig } = usePublicConfigQuery();
  const pathname = usePathname();
  const href = waContinueUrl(publicConfig?.whatsappNumber ?? "", vid, pageCodeFor(pathname ?? ""));

  if (!href) return null;

  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      data-testid="wa-continue"
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium",
        "text-[#128C7E] bg-[#25D366]/12 hover:bg-[#25D366]/20 transition-colors",
        className,
      )}
    >
      <MessageCircle className="h-3.5 w-3.5" aria-hidden="true" />
      Continue on WhatsApp
    </a>
  );
}
