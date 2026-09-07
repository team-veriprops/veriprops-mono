import { HttpClient } from "@lib/FetchHttpClient";
import { SuccessResponse } from "@/types/models";
import {
  AgentTrends,
  Funnel,
  RegionalRow,
  Revenue,
  TierTime,
  WhatsAppChannelAnalytics,
} from "@/types/analytics";

/**
 * Analytics API (PRD §18.1, D38). Mirrors the backend controller at
 * app/domain/analytics/controller.py — every figure is derived server-side; the
 * dashboard renders it, never recomputes it.
 */
export class AnalyticsService {
  constructor(private readonly http: HttpClient) {}

  getFunnel(): Promise<SuccessResponse<Funnel>> {
    return this.http.get(`/admin/analytics/funnel`);
  }

  getTimeByTier(): Promise<SuccessResponse<TierTime[]>> {
    return this.http.get(`/admin/analytics/time-by-tier`);
  }

  getRevenue(): Promise<SuccessResponse<Revenue>> {
    return this.http.get(`/admin/analytics/revenue`);
  }

  getRegional(): Promise<SuccessResponse<RegionalRow[]>> {
    return this.http.get(`/admin/analytics/regional`);
  }

  getAgentTrends(): Promise<SuccessResponse<AgentTrends>> {
    return this.http.get(`/admin/analytics/agent-trends`);
  }

  /**
   * §26.10's WhatsApp channel metrics over a trailing window (WA-43). `days` is optional —
   * omitted, the backend applies its configured default rather than the frontend guessing
   * one, so the window is the same everywhere it is quoted.
   */
  getWhatsAppChannel(days?: number): Promise<SuccessResponse<WhatsAppChannelAnalytics>> {
    const query = days ? `?days=${days}` : "";
    return this.http.get(`/admin/analytics/whatsapp${query}`);
  }

  /** Re-read Meta's quality rating, then return the whole panel (D81). */
  syncWhatsAppQuality(days?: number): Promise<SuccessResponse<WhatsAppChannelAnalytics>> {
    const query = days ? `?days=${days}` : "";
    return this.http.post(`/admin/analytics/whatsapp/quality/sync${query}`, {});
  }
}
