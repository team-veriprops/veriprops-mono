import { HttpClient } from "@lib/FetchHttpClient";
import { Page, SuccessResponse } from "@/types/models";
import {
  DecideRecheckRequest,
  Dispute,
  OpenDisputeRequest,
  Recheck,
  RequestRecheckRequest,
  RequestUpgradeRequest,
  ResolveDisputeRequest,
  Upgrade,
} from "@/types/revision";

/**
 * Revision / re-verification / dispute API (PRD §14). Mirrors the backend controllers at
 * app/domain/verification/{recheck,upgrade,dispute}. Customer, agent-defence, and admin
 * endpoints share one client; the hooks pick the relevant methods per surface.
 */
export class RevisionService {
  constructor(private readonly http: HttpClient) {}

  // ── Re-check (customer) ────────────────────────────────────────
  requestRecheck(verificationId: string, req: RequestRecheckRequest): Promise<SuccessResponse<Recheck>> {
    return this.http.post(`/verifications/${verificationId}/rechecks`, req);
  }
  listRechecks(verificationId: string): Promise<SuccessResponse<Recheck[]>> {
    return this.http.get(`/verifications/${verificationId}/rechecks`);
  }
  // ── Re-check (admin) ───────────────────────────────────────────
  listPendingRechecks(page = 0, pageSize = 10): Promise<SuccessResponse<Page<Recheck>>> {
    return this.http.get(`/admin/rechecks?page=${page}&page_size=${pageSize}`);
  }
  decideRecheck(recheckId: string, req: DecideRecheckRequest): Promise<SuccessResponse<Recheck>> {
    return this.http.post(`/admin/rechecks/${recheckId}/decide`, req);
  }

  // ── Tier upgrade (customer) ────────────────────────────────────
  requestUpgrade(verificationId: string, req: RequestUpgradeRequest): Promise<SuccessResponse<Upgrade>> {
    return this.http.post(`/verifications/${verificationId}/upgrades`, req);
  }
  listUpgrades(verificationId: string): Promise<SuccessResponse<Upgrade[]>> {
    return this.http.get(`/verifications/${verificationId}/upgrades`);
  }

  // ── Dispute (customer) ─────────────────────────────────────────
  openDispute(verificationId: string, req: OpenDisputeRequest): Promise<SuccessResponse<Dispute>> {
    return this.http.post(`/verifications/${verificationId}/disputes`, req);
  }
  listDisputes(verificationId: string): Promise<SuccessResponse<Dispute[]>> {
    return this.http.get(`/verifications/${verificationId}/disputes`);
  }
  // ── Dispute (agent defence, admin-mediated) ────────────────────
  listAgentDisputes(): Promise<SuccessResponse<Dispute[]>> {
    return this.http.get(`/agents/disputes`);
  }
  submitDefence(disputeId: string, text: string): Promise<SuccessResponse<Dispute>> {
    return this.http.post(`/agents/disputes/${disputeId}/defence`, { text });
  }
  // ── Dispute (admin) ────────────────────────────────────────────
  listOpenDisputes(page = 0, pageSize = 10): Promise<SuccessResponse<Page<Dispute>>> {
    return this.http.get(`/admin/disputes?page=${page}&page_size=${pageSize}`);
  }
  getDispute(disputeId: string): Promise<SuccessResponse<Dispute>> {
    return this.http.get(`/admin/disputes/${disputeId}`);
  }
  resolveDispute(disputeId: string, req: ResolveDisputeRequest): Promise<SuccessResponse<Dispute>> {
    return this.http.post(`/admin/disputes/${disputeId}/resolve`, req);
  }
}
