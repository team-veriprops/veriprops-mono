import { HttpClient } from "@lib/FetchHttpClient";
import { SuccessResponse } from "@/types/models";
import { HandoffContext, HandoffIntent, HandoffPayment, SeededDraft } from "@/types/handoff";
import { SetWhatsAppConsent, WhatsAppConsent } from "@/types/whatsappConsent";

/**
 * WhatsApp handoff API (PRD §26.4.2, §26.5). Mirrors the backend controller at
 * `app/domain/channel/whatsapp/handoff`.
 *
 * These endpoints are public — the handoff link is the authorization, not a session.
 * Redemption spends the link once and leaves an HttpOnly grant cookie behind, so the
 * follow-up calls carry no token: the browser holds the grant and the backend reads it.
 */
export class HandoffService {
  constructor(private readonly http: HttpClient) {}

  /** Spend a handoff link and get the context its landing page must acknowledge. */
  redeem(intent: HandoffIntent, token: string): Promise<SuccessResponse<HandoffContext>> {
    return this.http.post(
      `/public/wa/handoff/${intent}/${encodeURIComponent(token)}/redeem`,
    );
  }

  /**
   * Spend a chat-intake link and seed this customer's draft with the answers the bot
   * collected (§5.1, D69).
   *
   * The odd one out: it is **authenticated**, because the token carries a conversation
   * rather than an identity — the session is what says whose draft the answers become.
   */
  redeemIntake(token: string): Promise<SuccessResponse<SeededDraft>> {
    return this.http.post(`/wa/intake/${encodeURIComponent(token)}/redeem`);
  }

  /** Start payment for the case the grant names — never a case id from the client. */
  initiatePayment(): Promise<SuccessResponse<HandoffPayment>> {
    return this.http.post(`/public/wa/handoff/pay/initiate`);
  }

  /**
   * Record the §26.4.6 opt-ins from the payment landing (D76).
   *
   * This is the one moment a WhatsApp-native customer is asked — they arrived from a chat
   * link and may never open account settings. Grant-scoped like `initiatePayment`: the
   * customer comes from the grant cookie, never from this body.
   */
  setConsent(consent: SetWhatsAppConsent): Promise<SuccessResponse<WhatsAppConsent>> {
    return this.http.put(`/public/wa/handoff/pay/consent`, consent);
  }

  /** Drop the grant once its action is done, so it does not outlive its purpose. */
  release(): Promise<SuccessResponse<{ released: boolean }>> {
    return this.http.post(`/public/wa/handoff/release`);
  }
}
