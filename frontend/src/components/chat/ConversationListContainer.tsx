"use client";

import Link from "next/link";
import { MessageCircle, LifeBuoy } from "lucide-react";
import { ROUTES } from "@lib/routes";
import { Conversation, ConversationType } from "@/types/chat";
import { useConversationsQuery } from "./libs/useChatQueries";

/** Chat conversation list (§N.3) — all the user's threads, unread first. */
export default function ConversationListContainer() {
  const { data: conversations = [], isLoading } = useConversationsQuery();

  const sorted = [...conversations].sort((a, b) => {
    if (a.unread !== b.unread) return b.unread - a.unread;
    return (b.lastMessageAt ?? "").localeCompare(a.lastMessageAt ?? "");
  });

  return (
    <div className="max-w-2xl mx-auto p-6">
      <h1 className="text-xl font-semibold mb-1 text-brand-navy">
        Messages
      </h1>
      <p className="text-sm text-gray-500 mb-5">Your conversations with our team.</p>

      {isLoading && <p className="text-sm text-gray-400">Loading…</p>}
      {!isLoading && sorted.length === 0 && (
        <div className="text-center py-12 rounded-xl border border-black/5 bg-white">
          <MessageCircle className="w-8 h-8 mx-auto text-gray-300 mb-2" />
          <p className="text-sm text-gray-500">No conversations yet.</p>
          <Link href={ROUTES.PORTAL.SUPPORT} className="text-sm mt-2 inline-block text-brand-viridian">
            Contact support
          </Link>
        </div>
      )}

      <ul className="space-y-2">
        {sorted.map((c) => (
          <li key={c.id}>
            <Link
              href={hrefFor(c)}
              className="flex items-center gap-3 rounded-xl border border-black/5 bg-white px-4 py-3 hover:bg-black/2 transition-colors"
            >
              <div
                className="w-9 h-9 rounded-full flex items-center justify-center shrink-0 bg-brand-viridian/10 text-brand-viridian"
              >
                {c.type === ConversationType.GENERAL_SUPPORT ? (
                  <LifeBuoy className="w-4 h-4" />
                ) : (
                  <MessageCircle className="w-4 h-4" />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate text-brand-navy">
                  {titleFor(c)}
                </p>
                <p className="text-xs text-gray-400 truncate">{subtitleFor(c)}</p>
              </div>
              {c.unread > 0 && (
                <span
                  className="min-w-4.5 h-4.5 px-1 rounded-full text-[10px] font-bold text-white flex items-center justify-center bg-brand-viridian"
                >
                  {c.unread > 9 ? "9+" : c.unread}
                </span>
              )}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

function hrefFor(c: Conversation): string {
  if (c.type === ConversationType.GENERAL_SUPPORT) return ROUTES.PORTAL.SUPPORT;
  if (c.verificationId) return ROUTES.PORTAL.VERIFICATION_MESSAGES(c.verificationId);
  return ROUTES.PORTAL.CHAT;
}

function titleFor(c: Conversation): string {
  if (c.type === ConversationType.GENERAL_SUPPORT) return "General support";
  return c.subject ?? "Verification chat";
}

function subtitleFor(c: Conversation): string {
  if (c.type === ConversationType.CUSTOMER_ADMIN) return "You and the Veriprops team";
  if (c.type === ConversationType.GENERAL_SUPPORT) return "Account & billing help";
  return "Verification thread";
}
