"use client";

import { useMemo } from "react";
import ChatThread from "./ChatThread";
import { TaskState } from "@/types/agentTask";
import { useAgentTasksQuery } from "@components/agents/tasks/libs/useAgentTaskQueries";
import { useAgentThreadQuery, useSendMessageMutation } from "./libs/useChatQueries";

/**
 * Admin ↔ Agent thread, opened from a task (§11.1). The message is tagged to the task;
 * once the task is APPROVED the thread is read-only for the agent.
 */
export default function AgentMessagesContainer({ taskId }: { taskId: string }) {
  const { data, isLoading: tasksLoading } = useAgentTasksQuery(undefined, 0, 100);
  const task = useMemo(() => data?.items.find((t) => t.id === taskId), [data, taskId]);
  const verificationId = task?.verificationId ?? null;
  const readOnly = task?.state === TaskState.APPROVED;

  const { data: convo, isLoading } = useAgentThreadQuery(verificationId);
  const send = useSendMessageMutation("agent");

  return (
    <div className="flex flex-col gap-3 h-[70vh]">
      <div>
        <h1 className="text-lg font-semibold text-brand-navy">
          Task messages
        </h1>
        <p className="text-sm text-gray-500">
          Coordinate with admin about this task. Direct contact details are not permitted.
        </p>
      </div>
      {tasksLoading || isLoading ? (
        <p className="text-sm text-gray-400">Opening conversation…</p>
      ) : !verificationId ? (
        <p className="text-sm text-gray-400">Task not found.</p>
      ) : (
        <ChatThread
          conversationId={convo?.id ?? null}
          readOnly={readOnly}
          onSend={(body) => send.mutateAsync({ verificationId, body, taskId })}
        />
      )}
    </div>
  );
}
