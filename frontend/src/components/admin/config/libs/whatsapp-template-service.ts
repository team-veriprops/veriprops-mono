import { HttpClient } from "@lib/FetchHttpClient";
import { SuccessResponse } from "@/types/models";
import { WhatsAppTemplate, WhatsAppTemplateSyncResult } from "@/types/whatsappTemplate";

/**
 * Meta template registry API (PRD §26.7, WA-15/WA-41). Mirrors the backend controller at
 * `app/domain/channel/whatsapp/template`.
 *
 * Read plus a sync action, and no write: the template definitions are code-owned and the
 * approval status is Meta's, so there is nothing here an admin could edit that would mean
 * anything.
 */
export class WhatsAppTemplateService {
  constructor(private readonly http: HttpClient) {}

  /** The §26.7 set with Meta's latest verdict on each. */
  list(): Promise<SuccessResponse<WhatsAppTemplate[]>> {
    return this.http.get(`/admin/config/whatsapp-templates`);
  }

  /** Ask the configured transport what Meta currently says. */
  sync(): Promise<SuccessResponse<WhatsAppTemplateSyncResult>> {
    return this.http.post(`/admin/config/whatsapp-templates/sync`);
  }
}
