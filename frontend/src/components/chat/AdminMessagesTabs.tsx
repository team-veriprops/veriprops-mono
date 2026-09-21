"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { MessagesSquare, ShieldAlert } from "lucide-react";
import { PageShell } from "@components/ui/PageShell";
import AdminConversationsInboxContainer from "./AdminConversationsInboxContainer";
import HeldMessagesContainer from "./HeldMessagesContainer";
import { AdminMessagesTab, parseAdminMessagesTab } from "./libs/adminMessagesTab";
import { cn } from "@lib/utils";

const TABS: { id: AdminMessagesTab; label: string; icon: typeof ShieldAlert }[] = [
  { id: AdminMessagesTab.REVIEW, label: "Message review", icon: ShieldAlert },
  { id: AdminMessagesTab.CONVERSATIONS, label: "Conversations", icon: MessagesSquare },
];

/**
 * The admin messaging console (PRD §11.2, §16.5, §26.3.3).
 *
 * Two jobs on one page because they are the same job seen from two ends: the review queue
 * holds messages the fraud scan stopped, and the Conversations inbox is where the threads
 * those messages belong to are actually worked — cases, web support and WhatsApp alike.
 * Decision K puts every surface in one console, so splitting them across routes would be
 * the first crack in that. The tab lives in `?tab=` so the Chat button and notifications
 * can open the inbox directly.
 */
export default function AdminMessagesTabs() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const tab = parseAdminMessagesTab(searchParams.get("tab"));

  function selectTab(next: AdminMessagesTab) {
    const params = new URLSearchParams(searchParams.toString());
    params.set("tab", next);
    router.replace(`${pathname}?${params.toString()}`, { scroll: false });
  }

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
            onClick={() => selectTab(id)}
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

      {tab === AdminMessagesTab.REVIEW ? <HeldMessagesContainer /> : <AdminConversationsInboxContainer />}
    </PageShell>
  );
}
