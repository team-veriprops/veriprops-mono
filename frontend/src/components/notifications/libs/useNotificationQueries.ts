"use client";

import { useCallback } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { httpClient } from "@/containers";
import { useUserStream } from "@lib/useUserStream";
import { NotificationService } from "./notification-service";

const service = new NotificationService(httpClient);

export const notificationKeys = {
  list: (page: number) => ["notifications", "list", page] as const,
  unread: () => ["notifications", "unread"] as const,
  preferences: () => ["notifications", "preferences"] as const,
};

/**
 * Subscribes to the per-user SSE stream and invalidates the notification counter + feed on
 * any notification push. Mounted by the bell so the counter stays live app-wide (§4.9).
 */
export function useNotificationRealtime(enabled = true) {
  const qc = useQueryClient();
  const onEvent = useCallback(
    (evt: { event: string }) => {
      if (evt.event === "notification" || evt.event === "notification_unread") {
        qc.invalidateQueries({ queryKey: notificationKeys.unread() });
        qc.invalidateQueries({ queryKey: ["notifications", "list"] });
      }
    },
    [qc],
  );
  useUserStream({ onEvent, enabled });
}

export function useNotificationUnreadQuery(enabled = true) {
  return useQuery({
    queryKey: notificationKeys.unread(),
    enabled,
    queryFn: async () => (await service.unreadCount()).data?.count ?? 0,
    refetchInterval: 60_000,
  });
}

export function useNotificationsQuery(page = 0, enabled = true) {
  return useQuery({
    queryKey: notificationKeys.list(page),
    enabled,
    queryFn: async () => (await service.list(page)).data ?? null,
  });
}

export function useMarkNotificationReadMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (notificationId: string) => service.markRead(notificationId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: notificationKeys.unread() });
      qc.invalidateQueries({ queryKey: ["notifications", "list"] });
    },
  });
}

export function useMarkAllReadMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => service.markAllRead(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: notificationKeys.unread() });
      qc.invalidateQueries({ queryKey: ["notifications", "list"] });
    },
  });
}

export function useNotificationPreferencesQuery(enabled = true) {
  return useQuery({
    queryKey: notificationKeys.preferences(),
    enabled,
    queryFn: async () => (await service.listPreferences()).data ?? [],
  });
}

export function useSetPreferenceMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ eventType, emailEnabled, smsEnabled }: { eventType: string; emailEnabled: boolean; smsEnabled: boolean }) =>
      service.setPreference(eventType, emailEnabled, smsEnabled),
    onSuccess: () => qc.invalidateQueries({ queryKey: notificationKeys.preferences() }),
  });
}

export { service as notificationService };
