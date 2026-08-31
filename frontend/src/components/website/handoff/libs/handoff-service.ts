import { HttpClient } from "@lib/FetchHttpClient";
import { SuccessResponse } from "@/types/models";
import { HandoffContext, HandoffIntent, HandoffPayment } from "@/types/handoff";

/**
 * WhatsApp handoff API (PRD §7.4.2, §7.5). Mirrors the backend controller at
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

  /** Start payment for the case the grant names — never a case id from the client. */
  initiatePayment(): Promise<SuccessResponse<HandoffPayment>> {
    return this.http.post(`/public/wa/handoff/pay/initiate`);
  }

  /** Drop the grant once its action is done, so it does not outlive its purpose. */
  release(): Promise<SuccessResponse<{ released: boolean }>> {
    return this.http.post(`/public/wa/handoff/release`);
  }
}
