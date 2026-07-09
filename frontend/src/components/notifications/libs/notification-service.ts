import { HttpClient } from "@lib/FetchHttpClient";
import { Page, SuccessResponse } from "@/types/models";
import { AppNotification, NotificationPreference } from "@/types/notification";

/**
 * Notifications API. Mirrors the backend controllers at `app/domain/notification` and
 * `app/domain/notification_preference`. Delivery is over the per-user SSE stream (§4.9);
 * this is the durable feed + counter + preferences surface.
 */
export class NotificationService {
  constructor(private readonly http: HttpClient) {}

  list(page = 0, pageSize = 20): Promise<SuccessResponse<Page<AppNotification>>> {
    return this.http.get(`/notifications?page=${page}&pageSize=${pageSize}`);
  }

  unreadCount(): Promise<SuccessResponse<{ count: number }>> {
    return this.http.get(`/notifications/unread`);
  }

  markRead(notificationId: string): Promise<SuccessResponse<{ count: number }>> {
    return this.http.post(`/notifications/${notificationId}/read`);
  }

  markAllRead(): Promise<SuccessResponse<{ updated: number; count: number }>> {
    return this.http.post(`/notifications/read-all`);
  }

  // ── Preferences (§12.4) ─────────────────────────────────────────────

  listPreferences(): Promise<SuccessResponse<NotificationPreference[]>> {
    return this.http.get(`/notification-preferences`);
  }

  setPreference(
    eventType: string,
    emailEnabled: boolean,
    smsEnabled: boolean,
  ): Promise<SuccessResponse<NotificationPreference>> {
    return this.http.put(`/notification-preferences`, {
      eventType,
      emailEnabled,
      smsEnabled,
    });
  }
}
