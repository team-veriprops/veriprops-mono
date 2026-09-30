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

/** How one external channel behaves for one event (backend `ChannelMode`). */
export enum ChannelMode {
  UNUSED = "UNUSED",
  REQUIRED = "REQUIRED",
  OPTIONAL = "OPTIONAL",
}

/** One event the user may change (§12.4). The backend decides which events, their copy, and
 * each channel's mode; `*Enabled` is what will actually happen. */
export interface NotificationPreference {
  eventType: string;
  label: string;
  description: string;
  emailMode: ChannelMode;
  smsMode: ChannelMode;
  emailEnabled: boolean;
  smsEnabled: boolean;
}
