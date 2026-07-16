"use client";

import ChatThread from "./ChatThread";
import { MessageKind } from "@/types/chat";
import { useCustomerThreadQuery, useSendMessageMutation } from "./libs/useChatQueries";

/**
 * Customer ↔ Admin thread for one verification (§11.1). The customer may raise a
 * structured clarification request; delivery and holds are backend-owned.
 */
export default function CustomerMessagesContainer({ verificationId }: { verificationId: string }) {
  const { data: convo, isLoading } = useCustomerThreadQuery(verificationId);
  const send = useSendMessageMutation("customer");

  return (
    <div className="flex flex-col gap-3 h-[70vh]">
      <div>
        <h1 className="text-lg font-semibold text-brand-navy">
          Messages
        </h1>
        <p className="text-sm text-gray-500">
          Chat with our team about this verification. Messages are private and recorded.
        </p>
      </div>
      {isLoading ? (
        <p className="text-sm text-gray-400">Opening conversation…</p>
      ) : (
        <ChatThread
          conversationId={convo?.id ?? null}
          allowClarifications
          onSend={(body, kind) =>
            send.mutateAsync({ verificationId, body, kind: kind ?? MessageKind.CHAT })
          }
        />
      )}
    </div>
  );
}
