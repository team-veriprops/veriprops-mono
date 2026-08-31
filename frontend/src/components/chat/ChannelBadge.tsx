import { MessageSource } from "@/types/chat";
import { cn } from "@lib/utils";

/**
 * Source label for a conversation or message (PRD §7.3.3).
 *
 * WhatsApp and the website feed one admin console (Decision K), so an agent has to be
 * able to tell at a glance which surface a message arrived on — a reply goes back the
 * way it came, and the 24-hour service window only applies to one of them. The web
 * surface is the unremarkable default and stays unlabelled, so the badge means
 * "something to notice" rather than becoming visual noise on every row.
 */
export default function ChannelBadge({
  source,
  className,
}: {
  source?: MessageSource;
  className?: string;
}) {
  if (source !== MessageSource.WHATSAPP) return null;

  return (
    <span
      title="Received on WhatsApp"
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-1.5 py-0.5",
        "text-[10px] font-medium text-[#128C7E] bg-[#25D366]/12",
        className,
      )}
    >
      <span aria-hidden="true">WhatsApp</span>
      <span className="sr-only">Received on WhatsApp</span>
    </span>
  );
}
