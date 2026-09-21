"use client";

import { toast } from "sonner";

import WhatsAppOptInControls from "@components/shared/whatsapp/WhatsAppOptInControls";
import { getErrorMessage } from "@lib/utils";
import {
  NO_WHATSAPP_CONSENT,
  WhatsAppConsent,
  WhatsAppConsentSource,
} from "@/types/whatsappConsent";
import {
  useSetWhatsAppConsentMutation,
  useWhatsAppConsentQuery,
} from "./libs/useWhatsAppConsentQueries";

/**
 * Account → WhatsApp, the revocation half of §26.4.6.
 *
 * §26.4.6 requires both opt-ins to be revocable here as well as by a STOP keyword in chat.
 * The two routes are deliberately not symmetrical (D64): STOP revokes both and START
 * restores only progress updates, so **this page is the only place marketing consent can
 * be given back**. That is the reason it exists as its own card rather than as a line on
 * the linking form.
 *
 * It sits below the link card because consent without a linked number sends nothing — the
 * order on the page matches the order of the two things that have to be true.
 */
export default function WhatsAppConsentSettings() {
  const { data: consent, isLoading } = useWhatsAppConsentQuery();
  const save = useSetWhatsAppConsentMutation(WhatsAppConsentSource.ACCOUNT_SETTINGS);

  const onChange = async (next: WhatsAppConsent) => {
    try {
      await save.mutateAsync({ utility: next.utility, marketing: next.marketing });
    } catch (err) {
      toast.error(getErrorMessage(err as Error, "Could not save that preference."));
    }
  };

  return (
    <section
      className="rounded-xl bg-brand-surface-card p-5 shadow-card"
      data-testid="wa-consent-settings"
    >
      <h2 className="mb-1 text-base font-semibold text-brand-navy">Messages from us</h2>
      <p className="mb-4 text-sm text-brand-on-surface-variant">
        These control what we send to your linked WhatsApp number. Replying{" "}
        <strong>STOP</strong> in the chat switches both off; news and offers can only be
        switched back on here.
      </p>

      <WhatsAppOptInControls
        consent={consent ?? NO_WHATSAPP_CONSENT}
        onChange={onChange}
        disabled={isLoading || save.isPending}
      />
    </section>
  );
}
