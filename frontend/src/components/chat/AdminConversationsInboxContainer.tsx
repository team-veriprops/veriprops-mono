"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowLeft, ExternalLink, MessageCircle, Search, ShieldCheck } from "lucide-react";
import { DEFAULT_HISTORY_PAGE_SIZE } from "@lib/config/app";
import { useDebounce } from "@/hooks/useDebounce";
import ListPager from "@components/ui/ListPager";
import { AdminInboxFilter, Conversation, ConversationChannel, MessageSource } from "@/types/chat";
import AssistantModeBanner from "./AssistantModeBanner";
import ChannelBadge from "./ChannelBadge";
import ChatThread from "./ChatThread";
import {
  adminCaseMessagesHref,
  adminConversationSubtitle,
  adminConversationTitle,
} from "./libs/conversationLinks";
import { useAssistantReadinessQuery } from "./libs/useAssistantQueries";
import { useAdminConversationsQuery, useConversationSendMutation } from "./libs/useChatQueries";
import { cn } from "@lib/utils";

const PAGE_SIZE = DEFAULT_HISTORY_PAGE_SIZE;

const FILTERS: { value: AdminInboxFilter | null; label: string }[] = [
  { value: null, label: "All" },
  { value: AdminInboxFilter.SUPPORT, label: "Web support" },
  { value: AdminInboxFilter.WHATSAPP, label: "WhatsApp" },
  { value: AdminInboxFilter.CASES, label: "Cases" },
];

/**
 * The admin Conversations inbox (PRD §16.5, §26.3.3, Decision K).
 *
 * Every thread the console works — web support, WhatsApp enquiries and the two case
 * threads — in one list the backend pages, filters and searches. Unread is this admin's
 * own read state, so the list and the Chat counter agree. Replies go through
 * `useConversationSendMutation` (by conversation id): a support or WhatsApp thread has no
 * verification to send by.
 *
 * On any thread the assistant answers, its replies are in the thread as SYSTEM messages and
 * the mode banner shows who is answering — replying silences the assistant until handed
 * back (D57), which is invisible from the messages alone. The banner mounts for every
 * thread and hides itself where the assistant does not apply (an admin↔agent thread).
 */
export default function AdminConversationsInboxContainer() {
  const [page, setPage] = useState(0);
  const [filter, setFilter] = useState<AdminInboxFilter | null>(null);
  const [search, setSearch] = useState("");
  const query = useDebounce(search.trim(), 300);
  const { data, isLoading } = useAdminConversationsQuery({
    page,
    pageSize: PAGE_SIZE,
    filter: filter ?? undefined,
    query: query || undefined,
  });
  const { data: readiness } = useAssistantReadinessQuery();
  const send = useConversationSendMutation();
  const [selected, setSelected] = useState<Conversation | null>(null);

  const threads = data?.items ?? [];
  // The row carries fresh unread/read-only state after a refetch; the kept object only
  // stands in while the selected thread is on another page.
  const current = selected ? (threads.find((t) => t.id === selected.id) ?? selected) : null;
  const caseHref = current ? adminCaseMessagesHref(current) : null;

  function changeFilter(next: AdminInboxFilter | null) {
    setFilter(next);
    setPage(0);
  }

  return (
    <div className="flex flex-col gap-4">
      {readiness && (
        <p className="text-xs text-gray-600" data-testid="wa-bot-readiness">
          WhatsApp transport <span className="font-medium">{readiness.whatsappProvider}</span> · assistant model{" "}
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

      <div className="grid gap-4 md:grid-cols-[minmax(0,20rem)_1fr]">
        <section className={cn("flex min-w-0 flex-col gap-3", current && "hidden md:flex")}>
          <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filter conversations">
            {FILTERS.map(({ value, label }) => (
              <button
                key={label}
                type="button"
                aria-pressed={filter === value}
                data-testid={`admin-conversations-filter-${(value ?? "all").toLowerCase()}`}
                onClick={() => changeFilter(value)}
                className={cn(
                  "rounded-full border px-3 py-1 text-xs cursor-pointer transition-colors",
                  filter === value
                    ? "border-brand-viridian bg-brand-viridian text-white"
                    : "border-black/10 bg-white text-brand-navy hover:bg-black/3",
                )}
              >
                {label}
              </button>
            ))}
          </div>

          <label className="relative block">
            <span className="sr-only">Search conversations</span>
            <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-gray-400" aria-hidden="true" />
            <input
              type="search"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(0);
              }}
              placeholder="Name, email, number or subject"
              data-testid="admin-conversations-search"
              className="w-full rounded-lg border border-black/10 bg-white py-2 pl-8 pr-3 text-sm outline-none focus:border-brand-viridian"
            />
          </label>

          <ul className="space-y-1.5" data-testid="admin-conversations-threads">
            {isLoading && <li className="text-sm text-gray-600">Loading…</li>}
            {!isLoading && threads.length === 0 && (
              <li className="rounded-xl border border-black/5 bg-white px-4 py-8 text-center">
                <MessageCircle className="mx-auto mb-2 h-7 w-7 text-gray-300" />
                <p className="text-sm text-gray-600">
                  {query || filter ? "No conversations match." : "No conversations yet."}
                </p>
              </li>
            )}
            {threads.map((thread) => (
              <li key={thread.id}>
                <button
                  type="button"
                  onClick={() => setSelected(thread)}
                  data-testid="admin-conversation-row"
                  className={cn(
                    "flex w-full items-center gap-3 rounded-xl border px-3 py-2.5 text-left transition-colors cursor-pointer",
                    current?.id === thread.id
                      ? "border-brand-viridian/40 bg-brand-viridian/6"
                      : "border-black/5 bg-white hover:bg-black/2",
                  )}
                >
                  <div className="min-w-0 flex-1">
                    <p className="flex items-center gap-1.5 truncate text-sm font-medium text-brand-navy">
                      <span className="truncate">{adminConversationTitle(thread)}</span>
                      {thread.channel === ConversationChannel.WHATSAPP && (
                        <ChannelBadge source={MessageSource.WHATSAPP} />
                      )}
                    </p>
                    <p className="truncate text-xs text-gray-600">{adminConversationSubtitle(thread)}</p>
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

          <ListPager
            page={page}
            totalPages={data?.meta.totalPages ?? 0}
            onPageChange={setPage}
            testIdPrefix="admin-conversations-pager"
          />
        </section>

        <section className={cn("flex min-h-[60vh] min-w-0 flex-col gap-3", !current && "hidden md:flex")}>
          {current ? (
            <>
              <div className="flex items-center justify-between gap-2">
                <button
                  type="button"
                  onClick={() => setSelected(null)}
                  className="inline-flex items-center gap-1 text-sm text-brand-navy md:hidden cursor-pointer"
                >
                  <ArrowLeft className="h-4 w-4" aria-hidden="true" /> All conversations
                </button>
                <p className="hidden min-w-0 truncate text-sm font-medium text-brand-navy md:block">
                  {adminConversationTitle(current)}
                </p>
                {caseHref && (
                  <Link
                    href={caseHref}
                    className="inline-flex shrink-0 items-center gap-1 text-xs text-brand-viridian"
                    data-testid="admin-conversation-case-link"
                  >
                    Open case <ExternalLink className="h-3 w-3" aria-hidden="true" />
                  </Link>
                )}
              </div>
              <AssistantModeBanner conversationId={current.id} />
              <ChatThread
                conversationId={current.id}
                onSend={(body) => send.mutateAsync({ conversationId: current.id, body })}
                emptyHint="Nothing in this thread yet."
                assistantPending={current.assistantPending}
              />
            </>
          ) : (
            <div className="flex flex-1 items-center justify-center rounded-xl border border-black/5 bg-white">
              <p className="flex items-center gap-2 text-sm text-gray-600">
                <ShieldCheck className="h-4 w-4" aria-hidden="true" />
                Select a conversation to read it.
              </p>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
