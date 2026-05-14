"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { agentService } from "./useAgentApplicationQueries";
import type { TaskRole, Escalation, ActivityPage } from "./agent-service";

export const taskKeys = {
  available: (role: TaskRole, state?: string) =>
    ["agent", "tasks", "available", role, state ?? "all"] as const,
  active: ["agent", "tasks", "active"] as const,
  completed: ["agent", "tasks", "completed"] as const,
  detail: (taskId: string) => ["agent", "tasks", taskId] as const,
  history: (taskId: string, page: number) => ["agent", "tasks", taskId, "history", page] as const,
};

export function useAvailableTasks(role: TaskRole, state?: string) {
  return useQuery({
    queryKey: taskKeys.available(role, state),
    queryFn: () => agentService.getAvailableTasks(role, state),
    staleTime: 15_000,
  });
}

export function useActiveTasks() {
  return useQuery({
    queryKey: taskKeys.active,
    queryFn: () => agentService.getActiveTasks(),
    staleTime: 15_000,
  });
}

export function useCompletedTasks() {
  return useQuery({
    queryKey: taskKeys.completed,
    queryFn: () => agentService.getCompletedTasks(),
    staleTime: 30_000,
  });
}

export function useTask(taskId: string) {
  return useQuery({
    queryKey: taskKeys.detail(taskId),
    queryFn: () => agentService.getTask(taskId),
    staleTime: 10_000,
  });
}

export function useTaskHistory(taskId: string, page = 0) {
  return useQuery<{ data: ActivityPage }>({
    queryKey: taskKeys.history(taskId, page),
    queryFn: () => agentService.getTaskHistory(taskId, page),
    staleTime: 60_000,
  });
}

export function useAcceptTaskMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (taskId: string) => agentService.acceptTask(taskId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["agent", "tasks"] });
    },
  });
}

export function useDeclineTaskMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (taskId: string) => agentService.declineTask(taskId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["agent", "tasks"] });
    },
  });
}

export function useSaveDraftMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ taskId, payload }: { taskId: string; payload: Record<string, unknown> }) =>
      agentService.saveDraft(taskId, payload),
    onSuccess: (_data, { taskId }) =>
      qc.invalidateQueries({ queryKey: taskKeys.detail(taskId) }),
  });
}

export function useSubmitTaskMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ taskId, payload }: { taskId: string; payload: Record<string, unknown> }) =>
      agentService.submitTask(taskId, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["agent", "tasks"] });
    },
  });
}

export function useUploadEvidenceMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ taskId, formData }: { taskId: string; formData: FormData }) =>
      agentService.uploadEvidence(taskId, formData),
    onSuccess: (_data, { taskId }) =>
      qc.invalidateQueries({ queryKey: taskKeys.detail(taskId) }),
  });
}

export function useReportEscalationMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      taskId,
      category,
      description,
    }: {
      taskId: string;
      category: Escalation["category"];
      description: string;
    }) => agentService.reportEscalation(taskId, { category, description }),
    onSuccess: (_data, { taskId }) =>
      qc.invalidateQueries({ queryKey: taskKeys.detail(taskId) }),
  });
}
