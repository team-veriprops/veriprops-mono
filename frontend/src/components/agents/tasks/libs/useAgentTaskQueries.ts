"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { DEFAULT_PAGE_SIZE, DEFAULT_HISTORY_PAGE_SIZE } from "@lib/config/app";
import { httpClient } from "@/containers";
import { EvidenceKind } from "@/types/agentTask";
import { AgentTaskService } from "./agent-task-service";

const service = new AgentTaskService(httpClient);

export const agentTaskKeys = {
  list: (state: string | undefined, page: number, pageSize: number) =>
    ["agent", "tasks", state, page, pageSize] as const,
  evidence: (taskId: string) => ["agent", "tasks", taskId, "evidence"] as const,
  history: (taskId: string, page: number) => ["agent", "tasks", taskId, "history", page] as const,
  summary: () => ["agent", "tasks", "summary"] as const,
};

/** Agent task transition history (§19.3) — PII-safe, ownership-gated on the backend. */
export function useTaskHistoryQuery(taskId: string, page = 0) {
  return useQuery({
    queryKey: agentTaskKeys.history(taskId, page),
    queryFn: async () => (await service.getHistory(taskId, page, DEFAULT_HISTORY_PAGE_SIZE)).data ?? null,
  });
}

/** Agent dashboard summary (§7) — backend-derived counts over the agent's own tasks. */
export function useAgentDashboardQuery(enabled = true) {
  return useQuery({
    queryKey: agentTaskKeys.summary(),
    queryFn: async () => (await service.getSummary()).data ?? null,
    enabled,
  });
}

export function useAgentTasksQuery(state: string | undefined, page = 0, pageSize = DEFAULT_PAGE_SIZE) {
  return useQuery({
    queryKey: agentTaskKeys.list(state, page, pageSize),
    queryFn: async () => (await service.list(state, page, pageSize)).data ?? null,
    placeholderData: (prev) => prev,
  });
}

export function useTaskEvidenceQuery(taskId: string) {
  return useQuery({
    queryKey: agentTaskKeys.evidence(taskId),
    queryFn: async () => (await service.listEvidence(taskId)).data ?? [],
    enabled: !!taskId,
  });
}

function invalidate(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: ["agent", "tasks"] });
}

export function useAcceptTaskMutation() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: (taskId: string) => service.accept(taskId), onSuccess: () => invalidate(qc) });
}

export function useDeclineTaskMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ taskId, reason }: { taskId: string; reason?: string }) => service.decline(taskId, reason),
    onSuccess: () => invalidate(qc),
  });
}

export function useStartTaskMutation() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: (taskId: string) => service.start(taskId), onSuccess: () => invalidate(qc) });
}

export function useUploadEvidenceMutation(taskId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ file, kind, gps }: { file: File; kind: EvidenceKind; gps?: { latitude: number; longitude: number } }) =>
      service.uploadEvidence(taskId, file, kind, gps),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: agentTaskKeys.evidence(taskId) });
      invalidate(qc);
    },
  });
}

export function useSubmitTaskMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ taskId, payload }: { taskId: string; payload: Record<string, unknown> }) =>
      service.submit(taskId, payload),
    onSuccess: () => invalidate(qc),
  });
}

export { service as agentTaskService };
