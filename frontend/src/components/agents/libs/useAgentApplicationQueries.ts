"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { httpClient } from "@/containers";
import {
  AgentService,
  type AgentApplication,
  type BvnVerifyRequest,
  type CredentialsStepRequest,
  type KycDocumentsRequest,
  type SubmitApplicationRequest,
  type TypesStepRequest,
} from "./agent-service";

export const agentService = new AgentService(httpClient);

export const agentKeys = {
  application: ["agent", "application"] as const,
};

export function useAgentApplication(enabled = true) {
  return useQuery({
    queryKey: agentKeys.application,
    enabled,
    queryFn: async () => (await agentService.getMyApplication()).data ?? null,
    staleTime: 30_000,
  });
}

function patchCache(qc: ReturnType<typeof useQueryClient>, app?: AgentApplication | null) {
  if (app) qc.setQueryData(agentKeys.application, app);
  qc.invalidateQueries({ queryKey: agentKeys.application });
}

export function useSaveTypesStepMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (req: TypesStepRequest) => agentService.saveTypesStep(req),
    onSuccess: (res) => patchCache(qc, res.data),
  });
}

export function useVerifyBvnMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (req: BvnVerifyRequest) => agentService.verifyBvn(req),
    onSuccess: () => qc.invalidateQueries({ queryKey: agentKeys.application }),
  });
}

export function useUploadKycDocsMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (req: KycDocumentsRequest) => agentService.uploadKycDocs(req),
    onSuccess: (res) => patchCache(qc, res.data),
  });
}

export function useSaveCredentialsMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (req: CredentialsStepRequest) => agentService.saveCredentialsStep(req),
    onSuccess: (res) => patchCache(qc, res.data),
  });
}

export function useSubmitApplicationMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (req: SubmitApplicationRequest) => agentService.submitApplication(req),
    onSuccess: (res) => patchCache(qc, res.data),
  });
}
