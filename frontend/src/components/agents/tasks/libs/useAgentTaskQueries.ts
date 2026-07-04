"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { httpClient } from "@/containers";
import { EvidenceKind } from "@/types/agentTask";
import { AgentTaskService } from "./agent-task-service";

const service = new AgentTaskService(httpClient);

export const agentTaskKeys = {
  list: (state: string | undefined, page: number, pageSize: number) =>
    ["agent", "tasks", state, page, pageSize] as const,
  evidence: (taskId: string) => ["agent", "tasks", taskId, "evidence"] as const,
};

export function useAgentTasksQuery(state: string | undefined, page = 0, pageSize = 10) {
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
