import { HttpClient } from "@lib/FetchHttpClient";
import { SuccessResponse } from "@/types/models";
import { BotChannelReadiness, BotSession } from "@/types/chat";

/**
 * WhatsApp bot admin API. Mirrors `app/domain/channel/whatsapp/bot/session/controller.py`
 * (`/admin/whatsapp/bot`, CONFIGURE_SYSTEM).
 *
 * The hand-back is the load-bearing call: D57 makes a thread sticky-`HUMAN` the moment an
 * agent replies, and this is the only way out of it. Without it the first reply would
 * silence a customer's thread permanently.
 */
export class WhatsAppBotService {
  constructor(private readonly http: HttpClient) {}

  /** §7.11 — which transport and classifier are live, and whether one is configured. */
  readiness(): Promise<SuccessResponse<BotChannelReadiness>> {
    return this.http.get(`/admin/whatsapp/bot/readiness`);
  }

  session(phoneE164: string): Promise<SuccessResponse<BotSession>> {
    return this.http.get(`/admin/whatsapp/bot/sessions/${encodeURIComponent(phoneE164)}`);
  }

  handBack(phoneE164: string): Promise<SuccessResponse<BotSession>> {
    return this.http.post(
      `/admin/whatsapp/bot/sessions/${encodeURIComponent(phoneE164)}/hand-back`,
    );
  }
}
