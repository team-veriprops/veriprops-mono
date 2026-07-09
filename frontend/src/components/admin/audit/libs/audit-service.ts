import { HttpClient } from "@lib/FetchHttpClient";
import { SuccessResponse } from "@/types/models";
import { AdminActionLogPage } from "@/types/audit";
import { ROUTES } from "@/lib/routes";

/**
 * Admin audit API (PRD §19.1, §19.6). Mirrors app/domain/audit/controller.py.
 * The verification audit-pack export is a plain proxied download link, not a JSON call.
 */
export class AuditService {
  constructor(private readonly http: HttpClient) {}

  listAdminActions(
    actionTypes: string[] | undefined,
    page = 0,
    pageSize = 20,
  ): Promise<SuccessResponse<AdminActionLogPage>> {
    const q = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    (actionTypes ?? []).forEach((t) => q.append("action_types", t));
    return this.http.get(`/admin/audit/actions?${q.toString()}`);
  }

  /** Download link for the §19.3 legally-defensible audit pack (CSV) for a verification. */
  verificationPackUrl(verificationId: string): string {
    return ROUTES.ADMIN.VERIFICATION_AUDIT_EXPORT(verificationId);
  }
}
