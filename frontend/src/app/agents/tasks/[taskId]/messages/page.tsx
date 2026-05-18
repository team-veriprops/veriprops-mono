"use client";

import { use } from "react";
import { useQuery } from "@tanstack/react-query";
import { threadService } from "@components/shared/chat/libs/thread-service";
import ThreadView from "@components/shared/chat/ThreadView";
import { ArrowLeft, Loader2 } from "lucide-react";
import Link from "next/link";
import { ROUTES } from "@lib/routes";

export default function AgentTaskMessagesPage({
  params,
}: {
  params: Promise<{ taskId: string }>;
}) {
  const { taskId } = use(params);

  const { data, isLoading, error } = useQuery({
    queryKey: ["threads", "task", taskId],
    queryFn: () => threadService.getByTask(taskId),
    staleTime: 60_000,
  });

  const thread = (data as any)?.data ?? null;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-gray-200 bg-white">
        <Link
          href={ROUTES.AGENT.TASK_DETAIL(taskId)}
          className="text-gray-500 hover:text-gray-700"
        >
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <div>
          <h1 className="text-sm font-semibold text-gray-900">Task Chat</h1>
          <p className="text-xs text-gray-500">Task {taskId.slice(0, 8)}…</p>
        </div>
      </div>

      {/* Body */}
      {isLoading && (
        <div className="flex items-center justify-center flex-1">
          <Loader2 className="h-5 w-5 animate-spin text-indigo-600" />
        </div>
      )}
      {error && (
        <div className="flex items-center justify-center flex-1 text-sm text-red-600">
          Unable to load thread.
        </div>
      )}
      {thread && (
        <div className="flex-1 min-h-0">
          <ThreadView
            threadId={thread.id}
            currentRole="AGENT"
            placeholder="Message the admin team…"
          />
        </div>
      )}
    </div>
  );
}
