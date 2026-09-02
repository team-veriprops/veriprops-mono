import { HttpClient } from "@lib/FetchHttpClient";
import { SuccessResponse } from "@/types/models";
import {
  SetWhatsAppConsent,
  WhatsAppConsent,
  WhatsAppConsentSource,
} from "@/types/whatsappConsent";

/**
 * WhatsApp messaging consent API (PRD §7.4.6). Mirrors the backend controller at
 * `app/domain/channel/whatsapp/consent`.
 *
 * One endpoint pair serves both authenticated capture points — the payment step, where
 * §7.4.6 says the controls are first shown, and account settings, where they are
 * revocable. `source` rides as a query parameter rather than a body field so the record of
 * *where* a customer consented is a property of the call, not something a body could
 * misstate; the backend rejects the two chat-keyword sources outright.
 *
 * The `/wa/pay/<token>` landing has no session and writes through `HandoffService`
 * instead, on its grant.
 */
export class WhatsAppConsentService {
  constructor(private readonly http: HttpClient) {}

  /** This account's two opt-ins. Absent means both off — never inherited from silence. */
  get(): Promise<SuccessResponse<WhatsAppConsent>> {
    return this.http.get(`/channel/whatsapp/consent/me`);
  }

  /** Record both controls as the customer left them. */
  set(
    consent: SetWhatsAppConsent,
    source: WhatsAppConsentSource,
  ): Promise<SuccessResponse<WhatsAppConsent>> {
    return this.http.put(`/channel/whatsapp/consent/me?source=${source}`, consent);
  }
}
