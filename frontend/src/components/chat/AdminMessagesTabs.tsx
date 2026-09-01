"use client";

import { useState } from "react";
import { MessageSquare, ShieldAlert } from "lucide-react";
import { PageShell } from "@components/ui/PageShell";
import AdminWhatsAppInboxContainer from "./AdminWhatsAppInboxContainer";
import HeldMessagesContainer from "./HeldMessagesContainer";
import { cn } from "@lib/utils";

type MessagesTab = "review" | "whatsapp";

const TABS: { id: MessagesTab; label: string; icon: typeof ShieldAlert }[] = [
  { id: "review", label: "Message review", icon: ShieldAlert },
  { id: "whatsapp", label: "WhatsApp", icon: MessageSquare },
];

/**
 * The admin messaging console (PRD §11.2, §7.3.3).
 *
 * Two jobs on one page because they are the same job seen from two ends: the review queue
 * holds messages the fraud scan stopped, and the WhatsApp inbox is where the conversations
 * those messages belong to are actually had. Decision K puts every surface in one console,
 * so splitting them across routes would be the first crack in that.
 */
export default function AdminMessagesTabs() {
  const [tab, setTab] = useState<MessagesTab>("review");

  return (
    <PageShell
      title="Messages"
      description="Review held messages and reply to conversations from every surface."
    >
      <div
        className="mb-5 flex w-fit overflow-hidden rounded-lg border border-black/10 text-sm"
        role="tablist"
        aria-label="Messages sections"
      >
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={tab === id}
            data-testid={`admin-messages-tab-${id}`}
            onClick={() => setTab(id)}
            className={cn(
              "inline-flex items-center gap-1.5 px-3 py-1.5 cursor-pointer",
              tab === id ? "bg-brand-viridian text-white" : "text-brand-navy hover:bg-black/3",
            )}
          >
            <Icon className="h-3.5 w-3.5" aria-hidden="true" />
            {label}
          </button>
        ))}
      </div>

      {tab === "review" ? <HeldMessagesContainer /> : <AdminWhatsAppInboxContainer />}
    </PageShell>
  );
}
