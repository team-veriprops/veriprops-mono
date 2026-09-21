import { HttpClient } from "@lib/FetchHttpClient";
import { SuccessResponse } from "@/types/models";
import { AssistantReadiness, AssistantSession } from "@/types/chat";

/**
 * Assistant admin API. Mirrors `app/domain/communication/assistant/controller.py`
 * (`/admin/assistant`, `MANAGE_VERIFICATIONS` — the permission that lets an admin reply, so
 * every admin who can take a thread over can also see and undo it). Keyed by conversation
 * id (D93): the assistant answers a WhatsApp thread, a web support thread, and a case's
 * customer thread from the same state, not just phone numbers.
 *
 * The hand-back is the load-bearing call: D57 makes a thread sticky-`HUMAN` the moment an
 * agent replies, and this is the only way out of it. Without it the first reply would
 * silence a customer's thread permanently.
 */
export class AssistantService {
  constructor(private readonly http: HttpClient) {}

  /** §26.11 — which transport and classifier are live, and whether one is configured. */
  readiness(): Promise<SuccessResponse<AssistantReadiness>> {
    return this.http.get(`/admin/assistant/readiness`);
  }

  session(conversationId: string): Promise<SuccessResponse<AssistantSession>> {
    return this.http.get(`/admin/assistant/sessions/${conversationId}`);
  }

  handBack(conversationId: string): Promise<SuccessResponse<AssistantSession>> {
    return this.http.post(`/admin/assistant/sessions/${conversationId}/hand-back`);
  }
}
