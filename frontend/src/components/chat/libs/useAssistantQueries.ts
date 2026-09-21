"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { httpClient } from "@/containers";
import { REFETCH_INTERVAL_MS } from "@lib/config/app";
import { AssistantService } from "./assistant-service";

const service = new AssistantService(httpClient);

export const assistantKeys = {
  readiness: () => ["assistant", "readiness"] as const,
  session: (conversationId: string) => ["assistant", "session", conversationId] as const,
};

/**
 * The assistant's state for one conversation.
 *
 * Polled rather than read once: an agent's own reply flips the thread to `HUMAN` as a
 * side effect of sending (D57), so the banner has to notice a change it did not make.
 */
export function useAssistantSessionQuery(conversationId: string | null, enabled = true) {
  return useQuery({
    queryKey: assistantKeys.session(conversationId ?? "none"),
    enabled: !!conversationId && enabled,
    queryFn: async () => (await service.session(conversationId as string)).data ?? null,
    refetchInterval: REFETCH_INTERVAL_MS,
  });
}

export function useAssistantReadinessQuery(enabled = true) {
  return useQuery({
    queryKey: assistantKeys.readiness(),
    enabled,
    queryFn: async () => (await service.readiness()).data ?? null,
    refetchInterval: REFETCH_INTERVAL_MS,
  });
}

export function useHandBackMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (conversationId: string) => service.handBack(conversationId),
    onSuccess: (_result, conversationId) => {
      qc.invalidateQueries({ queryKey: assistantKeys.session(conversationId) });
      // The readiness card counts threads the assistant is silent on, so handing one back
      // changes it too.
      qc.invalidateQueries({ queryKey: assistantKeys.readiness() });
    },
  });
}

export { service as assistantService };
