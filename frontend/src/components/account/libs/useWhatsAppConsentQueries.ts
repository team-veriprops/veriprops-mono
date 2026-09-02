"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { httpClient } from "@/containers";
import {
  SetWhatsAppConsent,
  WhatsAppConsentSource,
  NO_WHATSAPP_CONSENT,
} from "@/types/whatsappConsent";
import { WhatsAppConsentService } from "./whatsapp-consent-service";

const service = new WhatsAppConsentService(httpClient);

export const whatsappConsentKeys = {
  me: ["whatsapp-consent", "me"] as const,
};

export function useWhatsAppConsentQuery() {
  return useQuery({
    queryKey: whatsappConsentKeys.me,
    // A customer with no record has consented to nothing (§7.4.6), so the empty case is a
    // real answer rather than a missing one — the controls render unticked either way.
    queryFn: async () => (await service.get()).data ?? NO_WHATSAPP_CONSENT,
  });
}

export function useSetWhatsAppConsentMutation(source: WhatsAppConsentSource) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (consent: SetWhatsAppConsent) =>
      (await service.set(consent, source)).data ?? null,
    onSuccess: () => qc.invalidateQueries({ queryKey: whatsappConsentKeys.me }),
  });
}

export { service as whatsappConsentService };
