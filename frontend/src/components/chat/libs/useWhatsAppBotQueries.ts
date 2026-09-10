"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { httpClient } from "@/containers";
import { REFETCH_INTERVAL_MS } from "@lib/config/app";
import { WhatsAppBotService } from "./whatsapp-bot-service";

const service = new WhatsAppBotService(httpClient);

export const whatsappBotKeys = {
  readiness: () => ["whatsapp-bot", "readiness"] as const,
  session: (phoneE164: string) => ["whatsapp-bot", "session", phoneE164] as const,
};

/**
 * The bot's state for one number.
 *
 * Polled rather than read once: an agent's own reply flips the thread to `HUMAN` as a
 * side effect of sending (D57), so the banner has to notice a change it did not make.
 */
export function useBotSessionQuery(phoneE164: string | null, enabled = true) {
  return useQuery({
    queryKey: whatsappBotKeys.session(phoneE164 ?? "none"),
    enabled: !!phoneE164 && enabled,
    queryFn: async () => (await service.session(phoneE164 as string)).data ?? null,
    refetchInterval: REFETCH_INTERVAL_MS,
  });
}

export function useBotReadinessQuery(enabled = true) {
  return useQuery({
    queryKey: whatsappBotKeys.readiness(),
    enabled,
    queryFn: async () => (await service.readiness()).data ?? null,
    refetchInterval: REFETCH_INTERVAL_MS,
  });
}

export function useHandBackMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (phoneE164: string) => service.handBack(phoneE164),
    onSuccess: (_result, phoneE164) => {
      qc.invalidateQueries({ queryKey: whatsappBotKeys.session(phoneE164) });
      // The readiness card counts threads the bot is silent on, so handing one back
      // changes it too.
      qc.invalidateQueries({ queryKey: whatsappBotKeys.readiness() });
    },
  });
}

export { service as whatsappBotService };
