"use client";

import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { ROUTES } from "@lib/routes";
import { ConversationChannel, MessageSource } from "@/types/chat";
import ChatThread from "./ChatThread";
import ChannelBadge from "./ChannelBadge";
import {
  conversationSubtitle,
  conversationTitle,
  readOnlyNotice,
} from "./libs/conversationLinks";
import { useConversationSendMutation, useConversationsQuery } from "./libs/useChatQueries";

/**
 * A customer's thread opened by id (§26.8) — the page for a thread with no case or support
 * page of its own, which today is their WhatsApp thread. The thread comes from the
 * customer's own conversation list, so an id they are not a member of simply isn't found;
 * whether it is read-only, and why, is backend-derived.
 */
export default function CustomerConversationContainer({
  conversationId,
}: {
  conversationId: string;
}) {
  const { data: conversations = [], isLoading } = useConversationsQuery();
  const send = useConversationSendMutation();
  const conversation = conversations.find((c) => c.id === conversationId);

  return (
    <div className="flex flex-col gap-3 h-[70vh]">
      <Link
        href={ROUTES.PORTAL.CHAT}
        className="inline-flex items-center gap-1 text-sm text-gray-600 hover:text-brand-navy w-fit"
      >
        <ArrowLeft className="w-4 h-4" aria-hidden="true" /> All conversations
      </Link>
      {isLoading ? (
        <p className="text-sm text-gray-600">Opening conversation…</p>
      ) : !conversation ? (
        <p className="text-sm text-gray-600" data-testid="chat-thread-not-found">
          This conversation isn&apos;t available.
        </p>
      ) : (
        <>
          <div>
            <h1 className="text-lg font-semibold text-brand-navy flex items-center gap-2">
              {conversationTitle(conversation)}
              {conversation.channel === ConversationChannel.WHATSAPP && (
                <ChannelBadge source={MessageSource.WHATSAPP} />
              )}
            </h1>
            <p className="text-sm text-gray-600">{conversationSubtitle(conversation)}</p>
          </div>
          <ChatThread
            conversationId={conversation.id}
            readOnly={!!conversation.readOnly}
            readOnlyNotice={
              conversation.readOnlyReason ? readOnlyNotice(conversation.readOnlyReason) : undefined
            }
            onSend={(body) => send.mutateAsync({ conversationId: conversation.id, body })}
            assistantPending={conversation.assistantPending}
          />
        </>
      )}
    </div>
  );
}
