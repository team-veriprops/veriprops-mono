"use client";

import { use, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { threadService } from "@components/shared/chat/libs/thread-service";
import ThreadView from "@components/shared/chat/ThreadView";
import { ArrowLeft, Loader2 } from "lucide-react";
import Link from "next/link";
import { ROUTES } from "@lib/routes";

type Panel = "customer" | "agent";

export default function AdminVerificationMessagesPage({
  params,
}: {
  params: Promise<{ vid: string }>;
}) {
  const { vid } = use(params);
  const [panel, setPanel] = useState<Panel>("customer");

  const customerThread = useQuery({
    queryKey: ["threads", "verification", vid],
    queryFn: () => threadService.getByVerification(vid),
    staleTime: 60_000,
  });

  const thread = (customerThread.data as any)?.data ?? null;

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)]">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-gray-200 bg-white">
        <Link
          href={ROUTES.ADMIN.VERIFICATION_DETAIL(vid)}
          className="text-gray-500 hover:text-gray-700"
        >
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <h1 className="text-sm font-semibold text-gray-900 flex-1">Thread — {vid}</h1>
        {/* Tab switcher */}
        <div className="flex rounded-lg border border-gray-200 overflow-hidden text-xs">
          <button
            onClick={() => setPanel("customer")}
            style={{ cursor: "pointer" }}
            className={`px-3 py-1.5 ${panel === "customer" ? "bg-indigo-600 text-white" : "bg-white text-gray-600 hover:bg-gray-50"}`}
            data-testid="thread-tab-customer"
          >
            Customer ↔ Admin
          </button>
          <button
            onClick={() => setPanel("agent")}
            style={{ cursor: "pointer" }}
            className={`px-3 py-1.5 ${panel === "agent" ? "bg-indigo-600 text-white" : "bg-white text-gray-600 hover:bg-gray-50"}`}
            data-testid="thread-tab-agent"
          >
            Admin ↔ Agent
          </button>
        </div>
      </div>

      {/* Body */}
      {customerThread.isLoading && (
        <div className="flex items-center justify-center flex-1">
          <Loader2 className="h-5 w-5 animate-spin text-indigo-600" />
        </div>
      )}
      {!customerThread.isLoading && thread && panel === "customer" && (
        <div className="flex-1 min-h-0">
          <ThreadView
            threadId={thread.id}
            currentRole="ADMIN"
            placeholder="Reply to customer…"
          />
        </div>
      )}
      {panel === "agent" && (
        <AgentThreadPanel verificationId={vid} />
      )}
    </div>
  );
}

function AgentThreadPanel({ verificationId }: { verificationId: string }) {
  return (
    <div className="flex flex-1 items-center justify-center text-sm text-gray-400">
      Select a task to view agent thread.
    </div>
  );
}
