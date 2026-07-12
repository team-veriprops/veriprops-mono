import { HttpClient } from "@lib/FetchHttpClient";
import { DEFAULT_HISTORY_PAGE_SIZE } from "@lib/config/app";
import { Page, SuccessResponse } from "@/types/models";
import { AgentDashboard, AgentTask, EvidenceItem, EvidenceKind } from "@/types/agentTask";
import { AuditActivityPage } from "@/types/audit";

/**
 * Agent task-execution API. Mirrors the backend controller at
 * `app/domain/verification/task/controller.py` (URL shape `/agents/tasks/...`).
 * Authorization is ownership-based on the backend; the agent identity is the session.
 */
export class AgentTaskService {
  private readonly base = "/agents/tasks";

  constructor(private readonly http: HttpClient) {}

  list(state: string | undefined, page: number, pageSize: number): Promise<SuccessResponse<Page<AgentTask>>> {
    const params = new URLSearchParams();
    if (state) params.set("state", state);
    params.set("page", String(page));
    params.set("page_size", String(pageSize));
    return this.http.get(`${this.base}?${params.toString()}`);
  }

  /** Agent home summary (§7) — backend-derived counts over the agent's own tasks. */
  getSummary(): Promise<SuccessResponse<AgentDashboard>> {
    return this.http.get(`${this.base}/summary`);
  }

  accept(taskId: string): Promise<SuccessResponse<AgentTask>> {
    return this.http.post(`${this.base}/${taskId}/accept`, {});
  }

  decline(taskId: string, reason?: string): Promise<SuccessResponse<AgentTask>> {
    return this.http.post(`${this.base}/${taskId}/decline`, { reason });
  }

  start(taskId: string): Promise<SuccessResponse<AgentTask>> {
    return this.http.post(`${this.base}/${taskId}/start`, {});
  }

  listEvidence(taskId: string): Promise<SuccessResponse<EvidenceItem[]>> {
    return this.http.get(`${this.base}/${taskId}/evidence`);
  }

  uploadEvidence(
    taskId: string,
    file: File,
    kind: EvidenceKind,
    gps?: { latitude: number; longitude: number },
  ): Promise<SuccessResponse<EvidenceItem>> {
    const form = new FormData();
    form.append("file", file);
    form.append("kind", kind);
    if (gps) {
      form.append("gps_latitude", String(gps.latitude));
      form.append("gps_longitude", String(gps.longitude));
    }
    return this.http.post(`${this.base}/${taskId}/evidence`, form);
  }

  submit(taskId: string, payload: Record<string, unknown>): Promise<SuccessResponse<AgentTask>> {
    return this.http.post(`${this.base}/${taskId}/submit`, { payload });
  }

  /** PII-safe state-transition history for one of the agent's own tasks (§19.3). */
  getHistory(taskId: string, page = 0, pageSize = DEFAULT_HISTORY_PAGE_SIZE): Promise<SuccessResponse<AuditActivityPage>> {
    return this.http.get(`${this.base}/${taskId}/history?page=${page}&page_size=${pageSize}`);
  }
}
