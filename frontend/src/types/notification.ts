/**
 * Notification types (PRD §12) — camelCase mirrors of `app/domain/notification` +
 * `app/domain/notification_preference`. Backend owns notification copy, links, and routing;
 * the frontend renders exactly what it receives.
 */

export interface AppNotification {
  id: string;
  type: string;
  title: string;
  body?: string | null;
  link?: string | null;
  read: boolean;
  eventRef?: string | null;
  dateCreated: string;
}

export interface NotificationPreference {
  eventType: string;
  emailEnabled: boolean;
  smsEnabled: boolean;
}
