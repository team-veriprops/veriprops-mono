import { httpClient } from "@/containers";

export interface Notification {
  id: string;
  recipientId: string;
  eventType: string;
  title: string;
  body: string;
  entityType: string | null;
  entityId: string | null;
  read: boolean;
  dateCreated: string;
}

export interface NotificationPreference {
  userId: string;
  eventType: string;
  emailEnabled: boolean;
  smsEnabled: boolean;
  pushEnabled: boolean;
}

export class NotificationService {
  list(limit = 30): Promise<{ data: Notification[] }> {
    return httpClient.get(`/notifications?limit=${limit}`);
  }

  markRead(id: string): Promise<{ data: null }> {
    return httpClient.post(`/notifications/${id}/read`);
  }

  getPreferences(): Promise<{ data: NotificationPreference[] }> {
    return httpClient.get("/notifications/preferences");
  }

  upsertPreference(pref: Omit<NotificationPreference, "userId">): Promise<{ data: NotificationPreference }> {
    return httpClient.put("/notifications/preferences", pref);
  }
}

export const notificationService = new NotificationService();
