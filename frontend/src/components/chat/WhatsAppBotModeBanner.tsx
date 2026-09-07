"use client";

import { Bot, Clock, User, Undo2 } from "lucide-react";
import { BotMode, EscalationReason } from "@/types/chat";
import { humanizeEnumLabel } from "@lib/utils";
import { cn } from "@lib/utils";
import { useBotSessionQuery, useHandBackMutation } from "./libs/useWhatsAppBotQueries";

/**
 * Who is answering this WhatsApp thread, and the way back (PRD §26.6, D57).
 *
 * A thread goes sticky-`HUMAN` the moment an agent replies, and stays there until someone
 * hands it back. That is deliberate — a bot talking over an agent mid-conversation is the
 * failure customers notice most — but it is also **invisible from the message list**: a
 * silent bot looks exactly like a working one. This banner is what makes the state legible
 * and reversible, so an agent who answered one question doesn't accidentally take a
 * customer off the bot forever.
 *
 * It carries the second invisible fact too: Meta's 24-hour service window (§26.7). Outside
 * it, a reply typed here is queued behind a `window_reopen` template rather than delivered
 * as written — which an agent needs to know *before* writing a long answer, not after.
 *
 * Admin-only: the endpoints behind it are `CONFIGURE_SYSTEM`-gated, and a 403 from the
 * shared HTTP client hard-navigates to `/forbidden`. Render it only on an admin surface.
 */
export default function WhatsAppBotModeBanner({
  phoneE164,
  className,
}: {
  phoneE164: string | null;
  className?: string;
}) {
  const { data: session, isLoading } = useBotSessionQuery(phoneE164);
  const handBack = useHandBackMutation();

  if (!phoneE164 || isLoading || !session) return null;

  const isHuman = session.mode === BotMode.HUMAN;

  return (
    <div
      data-testid="wa-bot-mode-banner"
      className={cn(
        "flex items-center gap-3 rounded-lg border px-3 py-2 text-sm",
        isHuman
          ? "border-amber-300/60 bg-amber-50 text-amber-900"
          : "border-black/5 bg-black/2 text-brand-navy",
        className,
      )}
    >
      <span
        className={cn(
          "flex h-7 w-7 shrink-0 items-center justify-center rounded-full",
          isHuman ? "bg-amber-500/15 text-amber-700" : "bg-brand-viridian/10 text-brand-viridian",
        )}
        aria-hidden="true"
      >
        {isHuman ? <User className="h-3.5 w-3.5" /> : <Bot className="h-3.5 w-3.5" />}
      </span>

      <div className="min-w-0 flex-1">
        <p className="font-medium" data-testid="wa-bot-mode-label">
          {isHuman ? "You're handling this thread" : "The assistant is answering"}
        </p>
        <p className="text-xs opacity-80">{describe(session.mode, session.lastEscalationReason)}</p>
      </div>

      {session.windowOpen === false && (
        <span
          data-testid="wa-window-closed"
          className={cn(
            "inline-flex shrink-0 items-center gap-1.5 rounded-md px-2 py-1",
            "bg-amber-500/15 text-[11px] font-medium text-amber-800",
          )}
          title={
            "Meta only delivers free text within 24 hours of the customer's last message. " +
            "Your reply is saved and sent automatically when they write back."
          }
        >
          <Clock className="h-3.5 w-3.5" aria-hidden="true" />
          Reply window closed
        </span>
      )}

      {isHuman && (
        <button
          type="button"
          data-testid="wa-bot-hand-back"
          onClick={() => handBack.mutate(phoneE164)}
          disabled={handBack.isPending}
          className={cn(
            "inline-flex shrink-0 items-center gap-1.5 rounded-md px-2.5 py-1.5",
            "text-xs font-medium text-white bg-brand-viridian",
            "hover:opacity-90 disabled:opacity-60 disabled:cursor-not-allowed cursor-pointer",
          )}
        >
          <Undo2 className="h-3.5 w-3.5" aria-hidden="true" />
          {handBack.isPending ? "Handing back…" : "Hand back to assistant"}
        </button>
      )}
    </div>
  );
}

/**
 * The sentence under the heading. When a thread is on a human, the escalation reason is
 * the useful part — "the customer asked for a person" and "the bot broke" call for very
 * different follow-ups.
 */
function describe(mode: BotMode, reason?: EscalationReason | null): string {
  if (mode === BotMode.HUMAN) {
    const because = reason ? ` Last handover: ${humanizeEnumLabel(reason).toLowerCase()}.` : "";
    return `The assistant stays quiet until you hand this thread back.${because}`;
  }
  return "It will step aside as soon as you reply here.";
}
