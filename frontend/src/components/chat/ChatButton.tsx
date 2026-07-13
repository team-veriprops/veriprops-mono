"use client";

import Link from "next/link";
import { MessageCircle } from "lucide-react";
import { ROUTES } from "@lib/routes";
import { useChatRealtime, useChatUnreadQuery } from "./libs/useChatQueries";
import { cn } from "@lib/utils";

/**
 * Chat entry in the top nav (PRD §N). Shows a counter of conversations with unread
 * messages (numeric, capped at "9+", hidden at zero) and opens the conversation list.
 * Mounts the per-user SSE subscription so the counter stays live app-wide (§4.9).
 */
export default function ChatButton({ dark = false }: { dark?: boolean }) {
  useChatRealtime();
  const { data: count = 0 } = useChatUnreadQuery();
  const badge = count > 9 ? "9+" : String(count);

  return (
    <Link
      href={ROUTES.PORTAL.CHAT}
      aria-label="Chat"
      data-testid="chat-button"
      className={cn(
        "relative w-9 h-9 rounded-lg flex items-center justify-center transition-colors duration-150 hover:bg-black/5",
        dark ? "text-white/80" : "text-brand-on-surface-variant",
      )}
    >
      <MessageCircle className="w-5 h-5" aria-hidden="true" />
      {count > 0 && (
        <span
          data-testid="chat-unread-badge"
          className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-1 rounded-full text-[10px] font-bold text-white flex items-center justify-center bg-brand-viridian"
        >
          {badge}
        </span>
      )}
    </Link>
  );
}
