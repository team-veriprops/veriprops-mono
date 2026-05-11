"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { adminService, adminKeys } from "@components/admin/libs/useAdminQueries";

export function useApproveTaskMutation(vid: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ taskId, note }: { taskId: string; note?: string }) =>
      adminService.approveTask(taskId, note),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: adminKeys.tasks(vid) });
      qc.invalidateQueries({ queryKey: adminKeys.verificationDetail(vid) });
    },
  });
}

export function useRejectTaskMutation(vid: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ taskId, reason }: { taskId: string; reason: string }) =>
      adminService.rejectTask(taskId, reason),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: adminKeys.tasks(vid) });
      qc.invalidateQueries({ queryKey: adminKeys.verificationDetail(vid) });
    },
  });
}

export function useReopenTaskMutation(vid: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ taskId, reason }: { taskId: string; reason: string }) =>
      adminService.reopenTask(taskId, reason),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: adminKeys.tasks(vid) });
      qc.invalidateQueries({ queryKey: adminKeys.verificationDetail(vid) });
    },
  });
}
