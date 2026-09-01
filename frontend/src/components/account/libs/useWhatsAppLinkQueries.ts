"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { httpClient } from "@/containers";
import { WhatsAppLinkService } from "./whatsapp-link-service";

const service = new WhatsAppLinkService(httpClient);

export const whatsappLinkKeys = {
  me: ["whatsapp-link", "me"] as const,
};

export function useWhatsAppLinkQuery() {
  return useQuery({
    queryKey: whatsappLinkKeys.me,
    queryFn: async () => (await service.get()).data ?? null,
  });
}

export function useStartWhatsAppLinkMutation() {
  return useMutation({
    mutationFn: async (phoneE164: string) => (await service.start(phoneE164)).data ?? null,
  });
}

export function useConfirmWhatsAppLinkMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (vars: { phoneE164: string; code: string }) =>
      (await service.confirm(vars.phoneE164, vars.code)).data ?? null,
    onSuccess: () => qc.invalidateQueries({ queryKey: whatsappLinkKeys.me }),
  });
}

export function useUnlinkWhatsAppMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => (await service.unlink()).data ?? null,
    onSuccess: () => qc.invalidateQueries({ queryKey: whatsappLinkKeys.me }),
  });
}

/**
 * The WhatsApp→web direction (§7.4.4). These carry the bot's signed token rather than a
 * number, so the landing page never gets to say which number it is claiming.
 */
export function useStartWhatsAppLinkFromTokenMutation() {
  return useMutation({
    mutationFn: async (token: string) => (await service.startFromToken(token)).data ?? null,
  });
}

export function useConfirmWhatsAppLinkFromTokenMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (vars: { token: string; code: string }) =>
      (await service.confirmFromToken(vars.token, vars.code)).data ?? null,
    onSuccess: () => qc.invalidateQueries({ queryKey: whatsappLinkKeys.me }),
  });
}

export { service as whatsappLinkService };
