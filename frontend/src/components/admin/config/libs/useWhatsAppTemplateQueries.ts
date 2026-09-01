"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { httpClient } from "@/containers";
import { WhatsAppTemplateService } from "./whatsapp-template-service";

const service = new WhatsAppTemplateService(httpClient);

export const whatsappTemplateKeys = { all: ["whatsapp-templates"] as const };

export function useWhatsAppTemplatesQuery() {
  return useQuery({
    queryKey: whatsappTemplateKeys.all,
    queryFn: async () => (await service.list()).data ?? [],
  });
}

export function useSyncWhatsAppTemplatesMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => (await service.sync()).data ?? null,
    // The sync writes statuses; the list is what renders them, so it has to re-read.
    onSuccess: () => qc.invalidateQueries({ queryKey: whatsappTemplateKeys.all }),
  });
}

export { service as whatsappTemplateService };
