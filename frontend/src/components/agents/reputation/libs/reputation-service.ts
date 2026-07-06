import { HttpClient } from "@lib/FetchHttpClient";
import { SuccessResponse } from "@/types/models";
import {
  AgentMetrics,
  AgentProfileSummary,
  AvailabilityStatus,
  CoverageArea,
  NigeriaLocations,
  SuggestedAgent,
} from "@/types/agentReputation";
import { AgentRole } from "@/types/agent";

/**
 * Agent reputation & coverage API (PRD §16). Mirrors
 * app/domain/user/agent/reputation/controller.py + the config locations endpoint. Also
 * carries the admin suggested-agents ranking used by the assignment picker.
 */
export class ReputationService {
  constructor(private readonly http: HttpClient) {}

  // ── Agent ──────────────────────────────────────────────────────
  getMetrics(): Promise<SuccessResponse<AgentMetrics>> {
    return this.http.get(`/agents/me/metrics`);
  }
  getProfile(): Promise<SuccessResponse<AgentProfileSummary>> {
    return this.http.get(`/agents/me/profile`);
  }
  setAvailability(availability: AvailabilityStatus): Promise<SuccessResponse<AvailabilityStatus>> {
    return this.http.put(`/agents/me/availability`, { availability });
  }
  getCoverage(): Promise<SuccessResponse<CoverageArea[]>> {
    return this.http.get(`/agents/me/coverage`);
  }
  setCoverage(areas: CoverageArea[]): Promise<SuccessResponse<CoverageArea[]>> {
    return this.http.put(`/agents/me/coverage`, areas);
  }

  // ── Reference data ─────────────────────────────────────────────
  getNigeriaLocations(): Promise<SuccessResponse<NigeriaLocations>> {
    return this.http.get(`/config/nigeria-locations`);
  }

  // ── Admin assignment ranking ───────────────────────────────────
  getSuggestedAgents(verificationId: string, role: AgentRole): Promise<SuccessResponse<SuggestedAgent[]>> {
    return this.http.get(`/admin/agents/suggested?verification_id=${verificationId}&role=${role}`);
  }
}
