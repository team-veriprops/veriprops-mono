"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Send, ShieldCheck, Info } from "lucide-react";
import { ChatMessage, MessageKind, SenderKind } from "@/types/chat";
import ChannelBadge from "./ChannelBadge";
import { useAuthStore } from "@components/website/auth/libs/useAuthStore";
import { usePublicConfigQuery } from "@components/website/auth/libs/useAuthQueries";
import { useMarkReadMutation, useMessagesQuery } from "./libs/useChatQueries";
import { cn } from "@lib/utils";

// Fallback until /config/public resolves; backend is the source of truth.
const DEFAULT_CHAT_MESSAGE_MAX_LENGTH = 2000;

interface ChatThreadProps {
  conversationId: string | null;
  onSend: (body: string, kind?: MessageKind) => Promise<unknown>;
  /** Customers may raise a structured clarification request (§11.1). */
  allowClarifications?: boolean;
  /** Agent thread for an approved task is read-only (§11.1). */
  readOnly?: boolean;
  emptyHint?: string;
}

/**
 * Shared, member-gated thread UI (PRD §11) — message list + composer. Delivery is live
 * over the per-user SSE stream (invalidated by the top-nav subscription) with a 60s poll
 * fallback. A held message shows its non-accusatory "being checked" notice to its sender.
 */
export default function ChatThread({
  conversationId,
  onSend,
  allowClarifications = false,
  readOnly = false,
  emptyHint = "No messages yet. Start the conversation.",
}: ChatThreadProps) {
  const session = useAuthStore((s) => s.session);
  const myId = session?.user?.id;
  const { data: publicConfig } = usePublicConfigQuery();
  const maxLength = publicConfig?.chatMessageMaxLength ?? DEFAULT_CHAT_MESSAGE_MAX_LENGTH;
  const { data, isLoading } = useMessagesQuery(conversationId, 0);
  const markRead = useMarkReadMutation();
  const [body, setBody] = useState("");
  const [asClarification, setAsClarification] = useState(false);
  const [sending, setSending] = useState(false);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  const messages = useMemo(() => data?.items ?? [], [data]);

  // Mark the thread read whenever it opens or new messages land (clears the Chat badge).
  useEffect(() => {
    if (conversationId) markRead.mutate(conversationId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversationId, messages.length]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages.length]);

  async function handleSend() {
    const trimmed = body.trim();
    if (!trimmed || sending) return;
    setSending(true);
    try {
      await onSend(
        trimmed,
        asClarification ? MessageKind.CLARIFICATION_REQUEST : MessageKind.CHAT,
      );
      setBody("");
      setAsClarification(false);
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="flex flex-col h-full min-h-96 rounded-xl border border-black/5 bg-white overflow-hidden">
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-3">
        {isLoading && <p className="text-sm text-gray-400">Loading…</p>}
        {!isLoading && messages.length === 0 && (
          <p className="text-sm text-gray-400 text-center py-8">{emptyHint}</p>
        )}
        {messages.map((m) => (
          <MessageBubble key={m.id} message={m} mine={!!myId && m.sender.userId === myId} />
        ))}
      </div>

      {readOnly ? (
        <div className="px-4 py-3 border-t border-black/5 bg-gray-50 text-xs text-gray-500 flex items-center gap-2">
          <Info className="w-3.5 h-3.5" /> This task is approved — its thread is now read-only.
        </div>
      ) : (
        <div className="border-t border-black/5 p-3">
          {allowClarifications && (
            <label className="flex items-center gap-2 mb-2 text-xs text-gray-500">
              <input
                type="checkbox"
                checked={asClarification}
                onChange={(e) => setAsClarification(e.target.checked)}
              />
              Send as a structured clarification request
            </label>
          )}
          <div className="flex items-end gap-2">
            <textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              rows={2}
              maxLength={maxLength}
              placeholder="Write a message…"
              data-testid="chat-composer"
              className="flex-1 resize-none rounded-lg border border-black/10 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-viridian/30"
            />
            <button
              onClick={handleSend}
              disabled={sending || !body.trim()}
              data-testid="chat-send"
              className="h-10 w-10 shrink-0 rounded-lg flex items-center justify-center text-white disabled:opacity-40 bg-brand-viridian"
              aria-label="Send message"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
          <p className="mt-1.5 text-[11px] text-gray-400 flex items-center gap-1">
            <ShieldCheck className="w-3 h-3" /> Messages are recorded and checked for your safety.
          </p>
        </div>
      )}
    </div>
  );
}

function MessageBubble({ message, mine }: { message: ChatMessage; mine: boolean }) {
  const isSystem = message.sender.kind === SenderKind.SYSTEM;
  if (isSystem) {
    return (
      <div className="text-center">
        <span className="inline-block rounded-full bg-gray-100 px-3 py-1 text-[11px] text-gray-500">
          {message.body}
        </span>
      </div>
    );
  }
  const name = message.sender.firstName ?? (mine ? "You" : "Participant");
  return (
    <div className={`flex ${mine ? "justify-end" : "justify-start"}`}>
      <div className={`max-w-[80%] ${mine ? "items-end" : "items-start"} flex flex-col`}>
        {!mine && (
          <span className="text-[11px] text-gray-400 mb-0.5 px-1 flex items-center gap-1.5">
            {name}
            <ChannelBadge source={message.source} />
          </span>
        )}
        <div
          className={cn(
            "rounded-2xl px-3.5 py-2 text-sm",
            mine ? "bg-brand-viridian text-white" : "bg-brand-surface-low text-brand-navy",
          )}
        >
          {message.body}
        </div>
        {message.heldNotice && (
          <span className="text-[11px] text-amber-600 mt-0.5 px-1">{message.heldNotice}</span>
        )}
      </div>
    </div>
  );
}
