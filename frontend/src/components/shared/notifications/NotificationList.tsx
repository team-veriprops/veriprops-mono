"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { notificationService, Notification } from "./libs/notification-service";
import { Bell } from "lucide-react";

const qKey = ["notifications"];

export function useNotifications() {
  return useQuery({
    queryKey: qKey,
    queryFn: () => notificationService.list(30),
    staleTime: 30_000,
    refetchInterval: 60_000,
  });
}

export default function NotificationList() {
  const qc = useQueryClient();
  const { data, isLoading } = useNotifications();
  const notifications: Notification[] = (data as any)?.data ?? [];

  const markRead = useMutation({
    mutationFn: (id: string) => notificationService.markRead(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: qKey }),
  });

  if (isLoading) return <div className="py-4 text-center text-xs text-gray-400">Loading…</div>;
  if (notifications.length === 0) {
    return <div className="py-6 text-center text-xs text-gray-400">No notifications</div>;
  }

  return (
    <ul className="divide-y divide-gray-100" data-testid="notification-list">
      {notifications.map((n) => (
        <li
          key={n.id}
          className={`px-4 py-3 cursor-pointer hover:bg-gray-50 ${!n.read ? "bg-indigo-50" : ""}`}
          onClick={() => !n.read && markRead.mutate(n.id)}
          data-testid="notification-item"
        >
          <p className={`text-sm font-medium ${!n.read ? "text-indigo-900" : "text-gray-700"}`}>{n.title}</p>
          <p className="text-xs text-gray-500 mt-0.5">{n.body}</p>
          <p className="text-[10px] text-gray-400 mt-1">{new Date(n.dateCreated).toLocaleString()}</p>
        </li>
      ))}
    </ul>
  );
}
