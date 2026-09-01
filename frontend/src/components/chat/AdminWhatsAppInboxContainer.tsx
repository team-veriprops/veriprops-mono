"use client";

import { useMemo, useState } from "react";
import { MessageCircle, ShieldCheck } from "lucide-react";
import { Conversation, ConversationChannel, MessageSource } from "@/types/chat";
import ChannelBadge from "./ChannelBadge";
import ChatThread from "./ChatThread";
import WhatsAppBotModeBanner from "./WhatsAppBotModeBanner";
import {
  useConversationSendMutation,
  useConversationsQuery,
} from "./libs/useChatQueries";
import { useBotReadinessQuery } from "./libs/useWhatsAppBotQueries";
import { cn } from "@lib/utils";

/**
 * The admin WhatsApp inbox (PRD §7.3.3, §7.8, Decision K).
 *
 * WhatsApp and the website feed **one** console, so this is not a second messaging app —
 * it is the same conversation list, filtered to the threads that arrived over WhatsApp,
 * where an agent can see what the bot said and take over. The bot's own replies are in
 * the thread as SYSTEM messages, which is what makes taking over mid-conversation
 * possible rather than blind.
 *
 * The mode banner is the important control here: replying silences the bot on that thread
 * until it is handed back (D57), and that state is invisible from the messages alone.
 */
export default function AdminWhatsAppInboxContainer() {
  const { data: conversations = [], isLoading } = useConversationsQuery();
  const { data: readiness } = useBotReadinessQuery();
  const send = useConversationSendMutation();
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const threads = useMemo(
    () =>
      conversations
        .filter((c) => c.channel === ConversationChannel.WHATSAPP)
        .sort((a, b) => {
          if (a.unread !== b.unread) return b.unread - a.unread;
          return (b.lastMessageAt ?? "").localeCompare(a.lastMessageAt ?? "");
        }),
    [conversations],
  );

  const selected = threads.find((t) => t.id === selectedId) ?? threads[0] ?? null;

  return (
    <div className="flex flex-col gap-4">
      {readiness && (
        <p className="text-xs text-gray-500" data-testid="wa-bot-readiness">
          Transport <span className="font-medium">{readiness.whatsappProvider}</span> · assistant{" "}
          <span className="font-medium">{readiness.intentProvider}</span>
          {!readiness.intentConfigured && (
            <span className="ml-1.5 text-amber-700">— no API key configured</span>
          )}
          {readiness.humanModeSessions > 0 && (
            <span className="ml-1.5">
              · {readiness.humanModeSessions} thread
              {readiness.humanModeSessions === 1 ? "" : "s"} off the assistant
            </span>
          )}
        </p>
      )}

      <div className="grid gap-4 md:grid-cols-[minmax(0,18rem)_1fr]">
        <ul className="space-y-1.5" data-testid="wa-inbox-threads">
          {isLoading && <li className="text-sm text-gray-400">Loading…</li>}
          {!isLoading && threads.length === 0 && (
            <li className="rounded-xl border border-black/5 bg-white px-4 py-8 text-center">
              <MessageCircle className="mx-auto mb-2 h-7 w-7 text-gray-300" />
              <p className="text-sm text-gray-500">No WhatsApp conversations yet.</p>
            </li>
          )}
          {threads.map((thread) => (
            <li key={thread.id}>
              <button
                type="button"
                onClick={() => setSelectedId(thread.id)}
                className={cn(
                  "flex w-full items-center gap-3 rounded-xl border px-3 py-2.5 text-left transition-colors cursor-pointer",
                  selected?.id === thread.id
                    ? "border-brand-viridian/40 bg-brand-viridian/6"
                    : "border-black/5 bg-white hover:bg-black/2",
                )}
              >
                <div className="min-w-0 flex-1">
                  <p className="flex items-center gap-1.5 truncate text-sm font-medium text-brand-navy">
                    <span className="truncate">{titleFor(thread)}</span>
                    <ChannelBadge source={MessageSource.WHATSAPP} />
                  </p>
                  <p className="truncate text-xs text-gray-400">
                    {thread.subject ?? "WhatsApp enquiry"}
                  </p>
                </div>
                {thread.unread > 0 && (
                  <span className="flex h-4.5 min-w-4.5 items-center justify-center rounded-full bg-brand-viridian px-1 text-[10px] font-bold text-white">
                    {thread.unread > 9 ? "9+" : thread.unread}
                  </span>
                )}
              </button>
            </li>
          ))}
        </ul>

        <div className="flex min-h-[60vh] flex-col gap-3">
          {selected ? (
            <>
              <WhatsAppBotModeBanner phoneE164={selected.externalRef ?? null} />
              <ChatThread
                conversationId={selected.id}
                onSend={(body) =>
                  send.mutateAsync({ conversationId: selected.id, body })
                }
                emptyHint="Nothing in this thread yet."
              />
            </>
          ) : (
            <div className="flex flex-1 items-center justify-center rounded-xl border border-black/5 bg-white">
              <p className="flex items-center gap-2 text-sm text-gray-400">
                <ShieldCheck className="h-4 w-4" aria-hidden="true" />
                Select a conversation to read it.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * A WhatsApp enquiry often arrives before we know who is sending it, so the number is the
 * only identity there is until the linking flow resolves one (§7.4.4).
 */
function titleFor(thread: Conversation): string {
  return thread.externalRef ?? "WhatsApp enquiry";
}
