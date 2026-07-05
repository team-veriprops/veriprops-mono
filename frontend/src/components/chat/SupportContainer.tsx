"use client";

import { useState } from "react";
import { ChevronDown, LifeBuoy } from "lucide-react";
import ChatThread from "./ChatThread";
import { faqs } from "@components/website/home.data";
import { useSendMessageMutation, useSupportThreadQuery } from "./libs/useChatQueries";

/**
 * Support page (§N.2) — FAQ plus routing into chat. General enquiries go to the user's
 * general-support thread; verification-specific support routes through that verification's
 * own thread (linked from the verification detail).
 */
export default function SupportContainer() {
  const { data: convo, isLoading } = useSupportThreadQuery();
  const send = useSendMessageMutation("support");
  const [open, setOpen] = useState<number | null>(0);

  return (
    <div className="max-w-3xl mx-auto p-6 space-y-8">
      <div className="flex items-center gap-3">
        <div
          className="w-10 h-10 rounded-full flex items-center justify-center"
          style={{ backgroundColor: "rgba(63,102,83,0.1)", color: "var(--brand-viridian)" }}
        >
          <LifeBuoy className="w-5 h-5" />
        </div>
        <div>
          <h1 className="text-xl font-semibold" style={{ color: "var(--brand-navy)" }}>
            Support
          </h1>
          <p className="text-sm text-gray-500">Find an answer, or start a conversation with our team.</p>
        </div>
      </div>

      <section>
        <h2 className="text-sm font-semibold mb-3 text-gray-500 uppercase tracking-wide">
          Frequently asked
        </h2>
        <div className="space-y-2">
          {faqs.map((f, i) => (
            <div key={i} className="rounded-xl border border-black/5 bg-white overflow-hidden">
              <button
                onClick={() => setOpen(open === i ? null : i)}
                className="w-full flex items-center justify-between gap-3 px-4 py-3 text-left"
              >
                <span className="text-sm font-medium" style={{ color: "var(--brand-navy)" }}>
                  {f.question}
                </span>
                <ChevronDown
                  className={`w-4 h-4 flex-shrink-0 transition-transform ${open === i ? "rotate-180" : ""}`}
                />
              </button>
              {open === i && <p className="px-4 pb-4 text-sm text-gray-600">{f.answer}</p>}
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2 className="text-sm font-semibold mb-3 text-gray-500 uppercase tracking-wide">
          Still need help?
        </h2>
        <p className="text-xs text-gray-400 mb-2">
          For help with a specific verification, open its own Messages thread. For account or
          billing questions, message us here.
        </p>
        {isLoading ? (
          <p className="text-sm text-gray-400">Opening support chat…</p>
        ) : (
          <div className="h-[50vh]">
            <ChatThread
              conversationId={convo?.id ?? null}
              onSend={(body) => send.mutateAsync({ verificationId: "", body })}
              emptyHint="How can we help? Send us a message."
            />
          </div>
        )}
      </section>
    </div>
  );
}
