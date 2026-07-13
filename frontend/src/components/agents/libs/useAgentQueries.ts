"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { SHORT_STALE_TIME_MS, LONG_STALE_TIME_MS } from "@lib/config/app";
import { httpClient } from "@/containers";
import { AgentService } from "./agent-service";
import { AgentRole, SubmitAgentApplicationRequest } from "@/types/agent";
import { LegalDocument, SuccessResponse } from "@/types/models";

const agentService = new AgentService(httpClient);

export const agentKeys = {
  draft: ["agent", "application", "draft"] as const,
  status: ["agent", "application", "status"] as const,
  applications: (status: string | undefined, page: number, pageSize: number, query: string) =>
    ["agent", "applications", status ?? "all", page, pageSize, query] as const,
  application: (id: string) => ["agent", "application", id] as const,
};

export function useAgentDraftQuery(enabled = true) {
  return useQuery({
    queryKey: agentKeys.draft,
    enabled,
    queryFn: async () => (await agentService.getDraft()).data ?? null,
    staleTime: SHORT_STALE_TIME_MS,
  });
}

export function useSaveAgentDraftMutation() {
  return useMutation({
    mutationFn: ({ step, payload }: { step: number; payload: Record<string, unknown> }) =>
      agentService.saveDraft(step, payload),
  });
}

export function useSubmitAgentApplicationMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: SubmitAgentApplicationRequest) => agentService.submit(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: agentKeys.status });
      qc.invalidateQueries({ queryKey: agentKeys.draft });
    },
  });
}

export function useAgentStatusQuery(enabled = true) {
  return useQuery({
    queryKey: agentKeys.status,
    enabled,
    queryFn: async () => (await agentService.getMyStatus()).data ?? null,
    staleTime: SHORT_STALE_TIME_MS,
  });
}

export function useAgentApplicationsQuery(
  status: string | undefined,
  page: number,
  pageSize: number,
  query = "",
) {
  return useQuery({
    queryKey: agentKeys.applications(status, page, pageSize, query),
    queryFn: () => agentService.listApplications(status, page, pageSize, query),
    placeholderData: (prev) => prev,
  });
}

export function useAgentApplicationQuery(id: string | null) {
  return useQuery({
    queryKey: agentKeys.application(id ?? "none"),
    enabled: !!id,
    queryFn: async () => (await agentService.getApplication(id as string)).data ?? null,
  });
}

export function useApproveAgentMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, approvedRoles }: { id: string; approvedRoles?: AgentRole[] }) =>
      agentService.approve(id, approvedRoles),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["agent", "applications"] }),
  });
}

export function useRejectAgentMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) => agentService.reject(id, reason),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["agent", "applications"] }),
  });
}

/** Current AGENT_TERMS version — backend is the source of truth (PRD §3.5). */
export function useAgentTermsQuery() {
  return useQuery({
    queryKey: ["agent", "terms"],
    queryFn: async () => {
      const res = await httpClient.get<SuccessResponse<LegalDocument>>(
        "/users/auth/consents/documents/agent-terms",
      );
      return res.data ?? null;
    },
    staleTime: LONG_STALE_TIME_MS,
  });
}

export { agentService };
