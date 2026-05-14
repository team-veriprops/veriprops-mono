import { HttpClient } from "@lib/FetchHttpClient";
import { SuccessResponse } from "@/types/models";
import type {
  AgentApplication,
} from "@components/agents/libs/agent-service";

export type AdminSubRole = "SUPER" | "OPERATIONS" | "FINANCE" | "CONTENT_CREATOR" | "CONTENT_APPROVER";
export type AdminInvitationStatus = "PENDING" | "ACCEPTED" | "EXPIRED" | "REVOKED";
export type AcceptInviteBranch =
  | "SIGNUP_REQUIRED"
  | "LOGIN_REQUIRED"
  | "ALREADY_ADMIN"
  | "ACCEPTED";

export interface AdminInvitation {
  id: string;
  email: string;
  subRole: AdminSubRole;
  status: AdminInvitationStatus;
  inviterAdminId: string;
  expiresAt: string;
  acceptedAt: string | null;
  dateCreated: string;
}

export interface InviteAdminResult {
  invitation: AdminInvitation;
  rawToken: string;
}

export interface AcceptInviteResult {
  branch: AcceptInviteBranch;
  email: string;
  subRole: AdminSubRole | null;
  firstName?: string;
  lastName?: string;
}

export interface PageResponse<T> {
  status: string;
  code: string;
  items: T[];
  meta: {
    page: number;
    pageSize: number;
    count: number;
    total: number;
  };
}

export interface AdminAgentApplication extends AgentApplication {
  idDocUrl: string | null;
  selfieUrl: string | null;
  surveyorLicenceUrl: string | null;
  nbaLicenceUrl: string | null;
  userFirstName: string | null;
  userLastName: string | null;
  userEmail: string | null;
}

// ── Verification admin types ──

export type VerificationStatus =
  | "DRAFT" | "PAID" | "IN_PROGRESS" | "UNDER_REVIEW" | "COMPLETED"
  | "CANCELLED" | "FAILED" | "PAUSED" | "FLAGGED";
export type VerificationTier = "BASIC" | "STANDARD" | "PREMIUM";

export interface VerificationNote {
  id: string;
  verificationId: string;
  adminId: string;
  content: string;
  tags: string[];
  pinned: boolean;
  dateCreated: string;
  dateUpdated: string | null;
}

export interface AdminVerificationListItem {
  id: string;
  vid: string;
  customerId: string;
  tier: VerificationTier;
  status: VerificationStatus;
  state: string | null;
  lga: string | null;
  addressLine: string | null;
  submittedAt: string | null;
  paidAt: string | null;
  dateCreated: string;
  dateUpdated: string | null;
}

export interface AdminVerificationDetail extends AdminVerificationListItem {
  property: Record<string, unknown> | null;
  pricing: Record<string, unknown> | null;
  notes: VerificationNote[];
  completedAt: string | null;
}

// ── Task types ──

export type TaskRole = "FIELD" | "SURVEYOR" | "REGISTRY" | "LAWYER";
export type TaskStatus =
  | "PENDING" | "ASSIGNED" | "ACCEPTED" | "IN_PROGRESS"
  | "SUBMITTED" | "APPROVED" | "REJECTED";

export interface Task {
  id: string;
  verificationId: string;
  role: TaskRole;
  agentId: string | null;
  status: TaskStatus;
  poolReleasedAt: string | null;
  acceptedAt: string | null;
  submittedAt: string | null;
  trustScore: number | null;
  draftPayload: Record<string, unknown> | null;
  dateCreated: string;
  dateUpdated: string | null;
}

export interface AvailableAgent {
  agentId: string;
  userId: string;
  firstName: string | null;
  lastName: string | null;
  types: string[];
  coverageStates: string[];
  activeTaskCount: number;
  rating: number | null;
  isTrusted: boolean;
}

// ── Conflict flag types (S29) ──

export type ConflictSeverity = "WARNING" | "BLOCKER";
export type ConflictStatus = "OPEN" | "OVERRIDDEN" | "TASK_REJECTED";

export interface ConflictFlag {
  id: string;
  verificationId: string;
  ruleId: string;
  severity: ConflictSeverity;
  description: string;
  status: ConflictStatus;
  resolutionNote: string | null;
  resolvedBy: string | null;
  resolvedAt: string | null;
  dateCreated: string;
  dateUpdated: string | null;
}

// ── Task review types (S28) ──

export type TaskReviewDecision = "APPROVED" | "REJECTED";

export interface TaskReviewResult {
  taskId: string;
  decision: TaskReviewDecision;
  reason: string | null;
  reviewedBy: string;
  reviewedAt: string;
}

// ── Trust score weight types (S30) ──

export interface TrustScoreWeightConfig {
  id: string;
  tier: string;
  role: string;
  weight: number;
  updatedBy: string | null;
  dateUpdated: string | null;
}

// ── Admin config types ──

export interface AdminConfig {
  id: string;
  key: string;
  value: string;
  description: string | null;
  updatedBy: string | null;
  dateUpdated: string | null;
}

// ── Analytics types (S53) ──

export interface MissionControlDto {
  activeVerifications: number;
  pendingAssignments: number;
  stuckJobs: number;
  slaAtRiskCount: number;
  revenueTotalNgn: number;
  availableAgents: number;
}

export interface RegionalStat {
  region: string;
  activeCount: number;
  completedCount: number;
  avgTrustScore: number | null;
  revenueNgn: number;
}

export interface RegionalPerformanceDto {
  regions: RegionalStat[];
}

export interface ConversionFunnelDto {
  signups: number;
  submitted: number;
  paid: number;
  completed: number;
  signupToPaidPct: number;
  paidToCompletedPct: number;
}

export interface AvgVerificationTimeByTierDto {
  tier: string;
  avgHours: number;
}

export interface AgentPerformanceTrendDto {
  period: string;
  avgQualityScore: number;
  totalScores: number;
}

export interface RevenueByLocationDto {
  state: string;
  tier: string;
  revenueNgn: number;
  count: number;
}

export interface DisputeRateDto {
  totalCompleted: number;
  totalDisputed: number;
  disputeRatePct: number;
}

export interface AnalyticsDashboardDto {
  conversionFunnel: ConversionFunnelDto;
  avgTimeByTier: AvgVerificationTimeByTierDto[];
  agentPerformanceTrends: AgentPerformanceTrendDto[];
  revenueByLocation: RevenueByLocationDto[];
  disputeRate: DisputeRateDto;
}

// ── Pricing types (S54) ──

export interface PricingLineItemDto {
  id?: string;
  label: string;
  amountMinor: number;
  description?: string;
  sortOrder: number;
}

export interface PricingTierConfigDto {
  id: string;
  tier: string;
  label: string;
  currency: string;
  serviceFeeMinor: number;
  isActive: boolean;
  lineItems: PricingLineItemDto[];
  updatedBy?: string | null;
  dateUpdated?: string | null;
}

export interface UpsertPricingTierPayload {
  tier: string;
  label: string;
  currency?: string;
  serviceFeeMinor: number;
  lineItems: Omit<PricingLineItemDto, "id">[];
}

export interface UpdatePricingTierPayload {
  label?: string;
  serviceFeeMinor?: number;
  isActive?: boolean;
}

export interface PricingUpgradeDeltaDto {
  id: string;
  fromTier: string;
  toTier: string;
  deltaMinor: number;
  currency: string;
  updatedBy?: string | null;
  dateUpdated?: string | null;
}

export interface UpsertUpgradeDeltaPayload {
  fromTier: string;
  toTier: string;
  deltaMinor: number;
  currency?: string;
}

// ── Finance / payment types (S54) ──

export type PaymentMethod = "CARD" | "BANK_TRANSFER" | "WIRE";
export type PaymentStatus =
  | "INITIATED" | "PROCESSING" | "SUCCEEDED" | "FAILED"
  | "PENDING_TRANSFER" | "PENDING_WIRE";

export interface PaymentDto {
  id: string;
  verificationId: string;
  provider: string;
  method: PaymentMethod;
  status: PaymentStatus;
  amountMinor: number;
  currency: string;
  providerRef?: string | null;
  failureReason?: string | null;
  wireProofUrl?: string | null;
  dateCreated: string;
  dateUpdated?: string | null;
}

// ── Commission breakdown types (S54) ──

export type EarningStatus = "PENDING" | "ON_HOLD" | "PAID";

export interface EarningDto {
  id: string;
  agentId: string;
  taskId: string;
  verificationId: string;
  grossAmount: number;
  commissionPct: number;
  netAmount: number;
  status: EarningStatus;
  computedAt: string;
  dateCreated: string;
}

// ── Content types (S55) ──

export type ContentItemType =
  | "HOW_IT_WORKS_STEP" | "FAQ" | "TESTIMONIAL"
  | "AGENT_SPOTLIGHT" | "AREA_INSIGHT";

export interface ContentItemDto {
  id: string;
  itemType: ContentItemType;
  slug: string;
  title: string;
  body: string;
  meta?: string | null;
  isPublished: boolean;
  sortOrder: number;
  authorId?: string | null;
  lga?: string | null;
  state?: string | null;
  dateCreated: string;
  dateUpdated?: string | null;
}

export interface CreateContentItemPayload {
  itemType: ContentItemType;
  slug: string;
  title: string;
  body: string;
  meta?: string;
  isPublished?: boolean;
  sortOrder?: number;
  lga?: string;
  state?: string;
}

export interface UpdateContentItemPayload {
  slug?: string;
  title?: string;
  body?: string;
  meta?: string;
  isPublished?: boolean;
  sortOrder?: number;
  lga?: string;
  state?: string;
}

// ── Broadcast types (S55) ──

export type BroadcastStatus = "DRAFT" | "SCHEDULED" | "SENDING" | "SENT" | "CANCELLED";
export type BroadcastAudience = "ALL" | "CUSTOMERS" | "AGENTS";

export interface BroadcastDto {
  id: string;
  subject: string;
  bodyText: string;
  bodyHtml?: string | null;
  audience: BroadcastAudience;
  channels?: string | null;
  status: BroadcastStatus;
  scheduledAt?: string | null;
  sentAt?: string | null;
  createdBy?: string | null;
  totalRecipients?: number | null;
  sentCount?: number | null;
  dateCreated: string;
  dateUpdated?: string | null;
}

export interface CreateBroadcastPayload {
  subject: string;
  bodyText: string;
  bodyHtml?: string;
  audience?: BroadcastAudience;
  channels?: string;
}

export interface PreviewBroadcastDto {
  subject: string;
  bodyText: string;
  bodyHtml?: string | null;
  audience: BroadcastAudience;
  estimatedRecipients: number;
}

export class AdminService {
  private readonly inviteBase = "/users/admin-invitations";
  private readonly agentBase = "/users/agents";
  private readonly verificationBase = "/admin/verifications";
  private readonly taskBase = "/admin";
  private readonly configBase = "/admin/config";

  constructor(private readonly http: HttpClient) {}

  // ── Admin invitations ──
  inviteAdmin(payload: {
    email: string;
    firstName: string;
    lastName: string;
    subRole: AdminSubRole;
  }): Promise<SuccessResponse<InviteAdminResult>> {
    return this.http.post(this.inviteBase, payload);
  }

  listInvitations(status?: AdminInvitationStatus): Promise<PageResponse<AdminInvitation>> {
    const qs = status ? `?status=${status}` : "";
    return this.http.get(`${this.inviteBase}${qs}`);
  }

  revokeInvitation(invitationId: string): Promise<SuccessResponse<boolean>> {
    return this.http.post(`${this.inviteBase}/${invitationId}/revoke`, {});
  }

  acceptInvitation(token: string): Promise<SuccessResponse<AcceptInviteResult>> {
    return this.http.post(`${this.inviteBase}/accept`, { token });
  }

  // ── Agent application queue ──
  listAgentApplications(opts?: {
    status?: "PENDING" | "APPROVED" | "REJECTED";
    page?: number;
    pageSize?: number;
  }): Promise<PageResponse<AdminAgentApplication>> {
    const params = new URLSearchParams();
    if (opts?.status) params.set("status", opts.status);
    if (opts?.page) params.set("page", String(opts.page));
    if (opts?.pageSize) params.set("page_size", String(opts.pageSize));
    const qs = params.toString();
    return this.http.get(`${this.agentBase}/admin/applications${qs ? `?${qs}` : ""}`);
  }

  approveApplication(applicationId: string): Promise<SuccessResponse<AdminAgentApplication>> {
    return this.http.post(`${this.agentBase}/admin/applications/${applicationId}/approve`, {});
  }

  rejectApplication(
    applicationId: string,
    reason: string,
  ): Promise<SuccessResponse<AdminAgentApplication>> {
    return this.http.post(`${this.agentBase}/admin/applications/${applicationId}/reject`, { reason });
  }

  // ── Admin verifications ──

  listVerifications(opts?: {
    status?: string;
    tier?: string;
    state?: string;
    lga?: string;
    vid?: string;
    page?: number;
    pageSize?: number;
  }): Promise<PageResponse<AdminVerificationListItem>> {
    const p = new URLSearchParams();
    if (opts?.status) p.set("status", opts.status);
    if (opts?.tier) p.set("tier", opts.tier);
    if (opts?.state) p.set("state", opts.state);
    if (opts?.lga) p.set("lga", opts.lga);
    if (opts?.vid) p.set("vid", opts.vid);
    if (opts?.page) p.set("page", String(opts.page));
    if (opts?.pageSize) p.set("page_size", String(opts.pageSize));
    const qs = p.toString();
    return this.http.get(`${this.verificationBase}${qs ? `?${qs}` : ""}`);
  }

  getVerification(vid: string): Promise<SuccessResponse<AdminVerificationDetail>> {
    return this.http.get(`${this.verificationBase}/${vid}`);
  }

  pauseVerification(vid: string): Promise<SuccessResponse<AdminVerificationDetail>> {
    return this.http.post(`${this.verificationBase}/${vid}/pause`, {});
  }

  resumeVerification(vid: string): Promise<SuccessResponse<AdminVerificationDetail>> {
    return this.http.post(`${this.verificationBase}/${vid}/resume`, {});
  }

  cancelVerification(vid: string): Promise<SuccessResponse<AdminVerificationDetail>> {
    return this.http.post(`${this.verificationBase}/${vid}/cancel`, {});
  }

  failVerification(vid: string, reason: string): Promise<SuccessResponse<AdminVerificationDetail>> {
    return this.http.post(`${this.verificationBase}/${vid}/fail`, { reason });
  }

  setDelay(vid: string, delayHours: number, reason: string): Promise<SuccessResponse<AdminVerificationDetail>> {
    return this.http.post(`${this.verificationBase}/${vid}/delay`, { delayHours, reason });
  }

  addNote(vid: string, payload: { content: string; tags: string[]; pinned: boolean }): Promise<SuccessResponse<VerificationNote>> {
    return this.http.post(`${this.verificationBase}/${vid}/notes`, payload);
  }

  updateNote(vid: string, noteId: string, payload: { pinned: boolean; tags: string[] }): Promise<SuccessResponse<VerificationNote>> {
    return this.http.put(`${this.verificationBase}/${vid}/notes/${noteId}`, payload);
  }

  releaseToPool(vid: string): Promise<SuccessResponse<AdminVerificationDetail>> {
    return this.http.post(`${this.verificationBase}/${vid}/release-to-pool`, {});
  }

  // ── Admin tasks ──

  listTasksForVerification(vid: string): Promise<SuccessResponse<Task[]>> {
    return this.http.get(`${this.taskBase}/verifications/${vid}/tasks`);
  }

  assignTask(vid: string, role: string, agentId: string): Promise<SuccessResponse<Task>> {
    return this.http.post(`${this.taskBase}/verifications/${vid}/tasks/${role}/assign`, { agentId });
  }

  reassignTask(taskId: string, agentId: string, note?: string): Promise<SuccessResponse<Task>> {
    return this.http.post(`${this.taskBase}/tasks/${taskId}/reassign`, { agentId, note });
  }

  listAvailableAgents(opts?: { role?: string; state?: string }): Promise<SuccessResponse<AvailableAgent[]>> {
    const p = new URLSearchParams();
    if (opts?.role) p.set("role", opts.role);
    if (opts?.state) p.set("state", opts.state);
    const qs = p.toString();
    return this.http.get(`${this.taskBase}/agents/available${qs ? `?${qs}` : ""}`);
  }

  // ── Conflict flags (S29) ──

  listConflicts(vid: string): Promise<SuccessResponse<ConflictFlag[]>> {
    return this.http.get(`${this.verificationBase}/${vid}/conflicts`);
  }

  resolveConflict(
    vid: string,
    conflictId: string,
    payload: { action: "OVERRIDE" | "REJECT_TASK"; note: string; taskIdToReject?: string },
  ): Promise<SuccessResponse<ConflictFlag>> {
    return this.http.post(
      `${this.verificationBase}/${vid}/conflicts/${conflictId}/resolve`,
      payload,
    );
  }

  // ── Task review (S28) ──

  approveTask(taskId: string, note?: string): Promise<SuccessResponse<TaskReviewResult>> {
    return this.http.post(`${this.taskBase}/tasks/${taskId}/approve`, { note: note ?? null });
  }

  rejectTask(taskId: string, reason: string): Promise<SuccessResponse<TaskReviewResult>> {
    return this.http.post(`${this.taskBase}/tasks/${taskId}/reject`, { reason });
  }

  reopenTask(taskId: string, reason: string): Promise<SuccessResponse<TaskReviewResult>> {
    return this.http.post(`${this.taskBase}/tasks/${taskId}/reopen`, { reason });
  }

  // ── Release (S31) ──

  releaseReport(vid: string): Promise<SuccessResponse<{ verificationId: string; vid: string; status: string; completedAt: string | null }>> {
    return this.http.post(`${this.verificationBase}/${vid}/release`, {});
  }

  failRelease(vid: string, reason: string): Promise<SuccessResponse<{ verificationId: string; vid: string; status: string }>> {
    return this.http.post(`${this.verificationBase}/${vid}/fail-release`, { reason });
  }

  // ── Trust score weights (S30) ──

  listTrustScoreWeights(): Promise<SuccessResponse<TrustScoreWeightConfig[]>> {
    return this.http.get("/admin/trust-score-weights");
  }

  setTierWeights(
    tier: string,
    weights: Record<string, number>,
  ): Promise<SuccessResponse<TrustScoreWeightConfig[]>> {
    return this.http.put(`/admin/trust-score-weights/${tier}`, { weights });
  }

  // ── Admin config ──

  listConfig(): Promise<SuccessResponse<AdminConfig[]>> {
    return this.http.get(this.configBase);
  }

  setConfig(key: string, value: string): Promise<SuccessResponse<AdminConfig>> {
    return this.http.put(`${this.configBase}/${key}`, { value });
  }

  // ── Analytics (S53) ──

  getMissionControl(): Promise<SuccessResponse<MissionControlDto>> {
    return this.http.get("/admin/analytics/mission-control");
  }

  getRegionalPerformance(): Promise<SuccessResponse<RegionalPerformanceDto>> {
    return this.http.get("/admin/analytics/regional-performance");
  }

  getAnalyticsDashboard(): Promise<SuccessResponse<AnalyticsDashboardDto>> {
    return this.http.get("/admin/analytics/dashboard");
  }

  // ── Pricing (S54) ──

  getPricingTiers(): Promise<SuccessResponse<PricingTierConfigDto[]>> {
    return this.http.get("/admin/pricing/tiers");
  }

  upsertPricingTier(payload: UpsertPricingTierPayload): Promise<SuccessResponse<PricingTierConfigDto>> {
    return this.http.post("/admin/pricing/tiers", payload);
  }

  updatePricingTier(tier: string, payload: UpdatePricingTierPayload): Promise<SuccessResponse<PricingTierConfigDto>> {
    return this.http.put(`/admin/pricing/tiers/${tier}`, payload);
  }

  getUpgradeDeltas(): Promise<SuccessResponse<PricingUpgradeDeltaDto[]>> {
    return this.http.get("/admin/pricing/upgrade-deltas");
  }

  upsertUpgradeDelta(payload: UpsertUpgradeDeltaPayload): Promise<SuccessResponse<PricingUpgradeDeltaDto>> {
    return this.http.put("/admin/pricing/upgrade-deltas", payload);
  }

  // ── Finance: payments (S54) ──

  adminListPayments(opts?: {
    status?: PaymentStatus;
    method?: PaymentMethod;
    page?: number;
    pageSize?: number;
  }): Promise<PageResponse<PaymentDto>> {
    const p = new URLSearchParams();
    if (opts?.status) p.set("status", opts.status);
    if (opts?.method) p.set("method", opts.method);
    if (opts?.page !== undefined) p.set("page", String(opts.page));
    if (opts?.pageSize) p.set("page_size", String(opts.pageSize));
    const qs = p.toString();
    return this.http.get(`/payments/admin/payments${qs ? `?${qs}` : ""}`);
  }

  confirmWirePayment(paymentId: string, note?: string): Promise<SuccessResponse<PaymentDto>> {
    return this.http.post(`/payments/admin/${paymentId}/confirm-wire`, { note: note ?? null });
  }

  // ── Finance: commissions (S54) ──

  adminListCommissions(opts?: {
    agentId?: string;
    status?: EarningStatus;
    page?: number;
    pageSize?: number;
  }): Promise<PageResponse<EarningDto>> {
    const p = new URLSearchParams();
    if (opts?.agentId) p.set("agent_id", opts.agentId);
    if (opts?.status) p.set("status", opts.status);
    if (opts?.page !== undefined) p.set("page", String(opts.page));
    if (opts?.pageSize) p.set("page_size", String(opts.pageSize));
    const qs = p.toString();
    return this.http.get(`/admin/commission/breakdown${qs ? `?${qs}` : ""}`);
  }

  // ── Content (S55) ──

  listContent(opts?: {
    itemType?: ContentItemType;
    publishedOnly?: boolean;
    page?: number;
    pageSize?: number;
  }): Promise<PageResponse<ContentItemDto>> {
    const p = new URLSearchParams();
    if (opts?.itemType) p.set("item_type", opts.itemType);
    if (opts?.publishedOnly !== undefined) p.set("published_only", String(opts.publishedOnly));
    if (opts?.page !== undefined) p.set("page", String(opts.page));
    if (opts?.pageSize) p.set("page_size", String(opts.pageSize));
    const qs = p.toString();
    return this.http.get(`/admin/content${qs ? `?${qs}` : ""}`);
  }

  createContentItem(payload: CreateContentItemPayload): Promise<SuccessResponse<ContentItemDto>> {
    return this.http.post("/admin/content", payload);
  }

  updateContentItem(itemId: string, payload: UpdateContentItemPayload): Promise<SuccessResponse<ContentItemDto>> {
    return this.http.put(`/admin/content/${itemId}`, payload);
  }

  publishContentItem(itemId: string, isPublished: boolean): Promise<SuccessResponse<ContentItemDto>> {
    return this.http.post(`/admin/content/${itemId}/publish`, { isPublished });
  }

  deleteContentItem(itemId: string): Promise<SuccessResponse<boolean>> {
    return this.http.delete(`/admin/content/${itemId}`);
  }

  reorderContentItems(itemIds: string[]): Promise<SuccessResponse<ContentItemDto[]>> {
    return this.http.post("/admin/content/reorder", { itemIds });
  }

  // ── Broadcasts (S55) ──

  listBroadcasts(opts?: { page?: number; pageSize?: number }): Promise<PageResponse<BroadcastDto>> {
    const p = new URLSearchParams();
    if (opts?.page !== undefined) p.set("page", String(opts.page));
    if (opts?.pageSize) p.set("page_size", String(opts.pageSize));
    const qs = p.toString();
    return this.http.get(`/admin/broadcasts${qs ? `?${qs}` : ""}`);
  }

  createBroadcast(payload: CreateBroadcastPayload): Promise<SuccessResponse<BroadcastDto>> {
    return this.http.post("/admin/broadcasts", payload);
  }

  updateBroadcast(broadcastId: string, payload: Partial<CreateBroadcastPayload>): Promise<SuccessResponse<BroadcastDto>> {
    return this.http.put(`/admin/broadcasts/${broadcastId}`, payload);
  }

  scheduleBroadcast(broadcastId: string, scheduledAt: string): Promise<SuccessResponse<BroadcastDto>> {
    return this.http.post(`/admin/broadcasts/${broadcastId}/schedule`, { scheduledAt });
  }

  sendBroadcastNow(broadcastId: string): Promise<SuccessResponse<BroadcastDto>> {
    return this.http.post(`/admin/broadcasts/${broadcastId}/send-now`, {});
  }

  cancelBroadcast(broadcastId: string): Promise<SuccessResponse<BroadcastDto>> {
    return this.http.post(`/admin/broadcasts/${broadcastId}/cancel`, {});
  }

  previewBroadcast(broadcastId: string): Promise<SuccessResponse<PreviewBroadcastDto>> {
    return this.http.get(`/admin/broadcasts/${broadcastId}/preview`);
  }
}
