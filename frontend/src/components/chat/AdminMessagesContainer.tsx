"use client";

import { useState } from "react";
import ChatThread from "./ChatThread";
import { ConversationType } from "@/types/chat";
import { useAdminThreadQuery, useSendMessageMutation } from "./libs/useChatQueries";
import { cn } from "@lib/utils";

const CHANNELS: { type: ConversationType; label: string }[] = [
  { type: ConversationType.CUSTOMER_ADMIN, label: "Customer" },
  { type: ConversationType.ADMIN_AGENT, label: "Agents" },
];

/**
 * Admin view of a verification's threads (§11.1) — switch between the Customer↔Admin and
 * Admin↔Agent channels. Admin sends are never fraud-held, but customer/agent messages are.
 */
export default function AdminMessagesContainer({ verificationId }: { verificationId: string }) {
  const [channel, setChannel] = useState<ConversationType>(ConversationType.CUSTOMER_ADMIN);
  const { data: convo, isLoading } = useAdminThreadQuery(verificationId, channel);
  const send = useSendMessageMutation("admin");

  return (
    <div className="flex flex-col gap-3 h-[70vh]">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <h1 className="text-lg font-semibold text-brand-navy">
          Messages
        </h1>
        <div className="flex rounded-lg border border-black/10 overflow-hidden text-sm">
          {CHANNELS.map((c) => (
            <button
              key={c.type}
              onClick={() => setChannel(c.type)}
              className={cn(
                "px-3 py-1.5",
                channel === c.type
                  ? "bg-brand-viridian text-white"
                  : "text-brand-navy"
              )}
            >
              {c.label}
            </button>
          ))}
        </div>
      </div>
      {isLoading ? (
        <p className="text-sm text-gray-400">Opening conversation…</p>
      ) : (
        <ChatThread
          conversationId={convo?.id ?? null}
          onSend={(body) => send.mutateAsync({ verificationId, body, type: channel })}
        />
      )}
    </div>
  );
}
