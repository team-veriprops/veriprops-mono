"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertCircle,
  Check,
  CheckCheck,
  Clock,
  Eye,
  Info,
  Mic,
  MonitorCheck,
  Paperclip,
  Send,
  ShieldCheck,
} from "lucide-react";
import { ChannelDeliveryStatus, ChatMessage, InboundKind, SenderKind } from "@/types/chat";
import { SuccessResponse } from "@/types/models";
import ChannelBadge from "./ChannelBadge";
import { useAuthStore } from "@components/website/auth/libs/useAuthStore";
import { usePublicConfigQuery } from "@components/website/auth/libs/useAuthQueries";
import { useMarkReadMutation, useMessagesQuery, useRunAssistantTurnMutation } from "./libs/useChatQueries";
import { cn, humanizeEnumLabel } from "@lib/utils";

// Fallback until /config/public resolves; backend is the source of truth.
const DEFAULT_CHAT_MESSAGE_MAX_LENGTH = 2000;

interface ChatThreadProps {
  conversationId: string | null;
  onSend: (body: string) => Promise<SuccessResponse<ChatMessage> | void>;
  /** History stays readable but nothing can be sent (an approved task, an unlinked number). */
  readOnly?: boolean;
  /** Why the thread is read-only — shown where the composer would be. */
  readOnlyNotice?: string;
  emptyHint?: string;
  /**
   * A web turn is waiting on the assistant's intent model (D93) — from `Conversation.
   * assistantPending`. Drives the typing indicator and, on a reload mid-turn, asks for the
   * turn exactly as a fresh send would, so a closed tab does not leave a customer waiting
   * on a reply nobody ever requested.
   */
  assistantPending?: boolean;
}

/**
 * Shared, member-gated thread UI (PRD §11) — message list + composer. Delivery is live
 * over the per-user SSE stream (invalidated by the top-nav subscription) with a 60s poll
 * fallback. A held message shows its non-accusatory "being checked" notice to its sender.
 */
export default function ChatThread({
  conversationId,
  onSend,
  readOnly = false,
  readOnlyNotice = "This conversation is read-only.",
  emptyHint = "No messages yet. Start the conversation.",
  assistantPending = false,
}: ChatThreadProps) {
  const session = useAuthStore((s) => s.session);
  const myId = session?.user?.id;
  const { data: publicConfig } = usePublicConfigQuery();
  const maxLength = publicConfig?.chatMessageMaxLength ?? DEFAULT_CHAT_MESSAGE_MAX_LENGTH;
  const { data, isLoading } = useMessagesQuery(conversationId, 0);
  const markRead = useMarkReadMutation();
  const runTurn = useRunAssistantTurnMutation();
  const [body, setBody] = useState("");
  const [sending, setSending] = useState(false);
  // A send below flagged its own reply as pending, ahead of the next poll of
  // `assistantPending`. Reset when the thread itself changes — it belongs to the last one
  // ("adjusting state during render" rather than an effect, per React's own guidance for
  // resetting state on a prop change).
  const [justSentPending, setJustSentPending] = useState(false);
  const [trackedConversationId, setTrackedConversationId] = useState(conversationId);
  if (conversationId !== trackedConversationId) {
    setTrackedConversationId(conversationId);
    setJustSentPending(false);
  }
  const awaitingTurn = assistantPending || justSentPending;
  const attemptedForRef = useRef<string | null>(null);
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

  // A turn left pending — by a send below, or found already pending on load, which is how
  // a reload after a closed tab recovers it (D93). Asked for once per episode (guarded by
  // the ref, not state, so this effect never sets state synchronously in its own body); if
  // the answer is itself still pending (lost the claim, or a newer message queued while
  // this one was answered), the next poll of `assistantPending` retries the same way.
  useEffect(() => {
    if (!conversationId || !awaitingTurn) {
      attemptedForRef.current = null;
      return;
    }
    if (attemptedForRef.current === conversationId) return;
    attemptedForRef.current = conversationId;
    runTurn.mutateAsync(conversationId).then((result) => {
      if (!result.data?.pending) setJustSentPending(false);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversationId, awaitingTurn]);

  async function handleSend() {
    const trimmed = body.trim();
    if (!trimmed || sending) return;
    setSending(true);
    try {
      const result = await onSend(trimmed);
      setBody("");
      if (result?.data?.assistantPending) setJustSentPending(true);
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="flex flex-col h-full min-h-96 rounded-xl border border-black/5 bg-white overflow-hidden">
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-3">
        {isLoading && <p className="text-sm text-gray-600">Loading…</p>}
        {!isLoading && messages.length === 0 && (
          <p className="text-sm text-gray-600 text-center py-8">{emptyHint}</p>
        )}
        {messages.map((m) => (
          <MessageBubble key={m.id} message={m} mine={!!myId && m.sender.userId === myId} />
        ))}
        {awaitingTurn && <AssistantTypingIndicator />}
      </div>

      {readOnly ? (
        <div
          data-testid="chat-read-only"
          className="px-4 py-3 border-t border-black/5 bg-gray-50 text-xs text-gray-600 flex items-center gap-2"
        >
          <Info className="w-3.5 h-3.5 shrink-0" aria-hidden="true" /> {readOnlyNotice}
        </div>
      ) : (
        <div className="border-t border-black/5 p-3">
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
          <p className="mt-1.5 text-[11px] text-gray-600 flex items-center gap-1">
            <ShieldCheck className="w-3 h-3" /> Messages are recorded and checked for your safety.
          </p>
        </div>
      )}
    </div>
  );
}

/** The assistant is working on a deferred turn (D93) — the same visual family as a SYSTEM
 * reply, since that is what it becomes once it lands. */
function AssistantTypingIndicator() {
  return (
    <div className="text-center" data-testid="chat-assistant-typing">
      <span className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-3 py-1.5 text-[11px] text-gray-600">
        <span className="flex gap-0.5">
          <span className="h-1 w-1 animate-bounce rounded-full bg-gray-400 [animation-delay:-0.3s]" />
          <span className="h-1 w-1 animate-bounce rounded-full bg-gray-400 [animation-delay:-0.15s]" />
          <span className="h-1 w-1 animate-bounce rounded-full bg-gray-400" />
        </span>
      </span>
    </div>
  );
}

function MessageBubble({ message, mine }: { message: ChatMessage; mine: boolean }) {
  const isSystem = message.sender.kind === SenderKind.SYSTEM;
  if (isSystem) {
    return (
      <div className="text-center">
        <span className="inline-block rounded-full bg-gray-100 px-3 py-1 text-[11px] text-gray-600">
          {message.body}
        </span>
        {message.channelStatus && (
          <div className="mt-0.5 flex justify-center">
            <DeliveryTicks status={message.channelStatus} />
          </div>
        )}
      </div>
    );
  }
  const name = message.sender.firstName ?? (mine ? "You" : "Participant");
  return (
    <div className={`flex ${mine ? "justify-end" : "justify-start"}`}>
      <div className={`max-w-[80%] ${mine ? "items-end" : "items-start"} flex flex-col`}>
        {!mine && (
          <span className="text-[11px] text-gray-600 mb-0.5 px-1 flex items-center gap-1.5">
            {name}
            <ChannelBadge source={message.source} />
            {message.unofficialMedia && (
              <span
                data-testid="chat-unofficial-media"
                className="inline-flex items-center gap-1 rounded-full bg-amber-500/12 px-1.5 py-0.5 text-[10px] font-medium text-amber-800"
                title={
                  "Sent over WhatsApp. Only uploads made on veriprops.ng enter the " +
                  "verification file (§26.1.6)."
                }
              >
                {message.mediaKind === InboundKind.AUDIO ? (
                  <Mic className="h-2.5 w-2.5" aria-hidden="true" />
                ) : (
                  <Paperclip className="h-2.5 w-2.5" aria-hidden="true" />
                )}
                {humanizeEnumLabel(message.mediaKind ?? InboundKind.UNSUPPORTED)} · not evidence
              </span>
            )}
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
        {/*
          §26.7 — written here, not yet delivered. Meta only carries free text within 24
          hours of the customer's last message, so this reply waits for their next one.
          Without the marker an agent has no way to tell it apart from a sent message.
        */}
        {message.pendingChannelDelivery && (
          <span
            data-testid="chat-pending-channel-delivery"
            className="mt-0.5 flex items-center gap-1 px-1 text-[11px] text-amber-600"
          >
            <Clock className="h-3 w-3" aria-hidden="true" />
            Waiting for the customer to reply before this can be delivered
          </span>
        )}
        {message.channelStatus && <DeliveryTicks status={message.channelStatus} />}
        {mine && message.seenBySupport && (
          <span
            data-testid="chat-seen-by-support"
            className="mt-0.5 flex items-center gap-1 px-1 text-[11px] text-gray-600"
          >
            <Eye className="h-3 w-3" aria-hidden="true" />
            Seen
          </span>
        )}
      </div>
    </div>
  );
}

const DELIVERY_TICKS: Record<
  ChannelDeliveryStatus,
  { icon: typeof Check; label: string; className: string }
> = {
  [ChannelDeliveryStatus.SENT]: { icon: Check, label: "Sent to WhatsApp", className: "text-gray-600" },
  [ChannelDeliveryStatus.DELIVERED]: {
    icon: CheckCheck,
    label: "Delivered on WhatsApp",
    className: "text-gray-600",
  },
  [ChannelDeliveryStatus.READ]: {
    icon: CheckCheck,
    label: "Read on WhatsApp",
    className: "text-brand-viridian",
  },
  [ChannelDeliveryStatus.FAILED]: {
    icon: AlertCircle,
    label: "Not delivered on WhatsApp",
    className: "text-danger",
  },
  // D92 — the customer read it in the portal first, so it was never sent to their phone.
  [ChannelDeliveryStatus.CANCELLED]: {
    icon: MonitorCheck,
    label: "Read on the website — not sent to WhatsApp",
    className: "text-gray-600",
  },
};

/**
 * How far a message got on the customer's WhatsApp (D92). The backend sends a status only
 * to the console, so this never appears on a customer's screen. The words say the same as
 * the icon's colour, for anyone who cannot tell grey ticks from green ones.
 */
function DeliveryTicks({ status }: { status: ChannelDeliveryStatus }) {
  const { icon: Icon, label, className } = DELIVERY_TICKS[status];
  return (
    <span
      data-testid="chat-channel-status"
      data-status={status}
      className={cn("mt-0.5 flex items-center gap-1 px-1 text-[11px]", className)}
    >
      <Icon className="h-3 w-3" aria-hidden="true" />
      {label}
    </span>
  );
}
