import { HttpClient } from "@lib/FetchHttpClient";
import { SuccessResponse } from "@/types/models";
import { WhatsAppLink, WhatsAppLinkChallenge } from "@/types/whatsappLink";

/**
 * WhatsApp account-linking API (PRD §26.4.4). Mirrors the backend controller at
 * `app/domain/channel/whatsapp/link`.
 *
 * Two directions, one confirm step. The `/me/*` pair is web→WhatsApp: the customer names
 * the number. The `/from-token/*` pair is WhatsApp→web: the **bot** named it, and it
 * travels inside the signed link — which is why those calls send a token and never a
 * number. Posting a number there would hand the browser back the power the token exists
 * to take away from it.
 */
export class WhatsAppLinkService {
  constructor(private readonly http: HttpClient) {}

  /** This account's link, in whatever state it is in. */
  get(): Promise<SuccessResponse<WhatsAppLink>> {
    return this.http.get(`/channel/whatsapp/link/me`);
  }

  /** Send a linking code to the number over WhatsApp. */
  start(phoneE164: string): Promise<SuccessResponse<WhatsAppLinkChallenge>> {
    return this.http.post(`/channel/whatsapp/link/me/start`, { phoneE164 });
  }

  /** Prove control of the number and establish the link. */
  confirm(phoneE164: string, code: string): Promise<SuccessResponse<WhatsAppLink>> {
    return this.http.post(`/channel/whatsapp/link/me/confirm`, { phoneE164, code });
  }

  /** Drop the link. The WhatsApp thread goes cold immediately. */
  unlink(): Promise<SuccessResponse<{ unlinked: boolean }>> {
    return this.http.delete(`/channel/whatsapp/link/me`);
  }

  /** Begin the WhatsApp→web direction — the number comes out of the bot's link. */
  startFromToken(token: string): Promise<SuccessResponse<WhatsAppLinkChallenge>> {
    return this.http.post(`/channel/whatsapp/link/from-token/start`, { token });
  }

  /** Complete the WhatsApp→web direction, spending the bot's link exactly once. */
  confirmFromToken(token: string, code: string): Promise<SuccessResponse<WhatsAppLink>> {
    return this.http.post(`/channel/whatsapp/link/from-token/confirm`, { token, code });
  }
}
