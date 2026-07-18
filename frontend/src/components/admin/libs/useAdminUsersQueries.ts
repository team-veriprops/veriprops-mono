"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { httpClient } from "@/containers";
import { TrustStatus } from "@components/website/auth/models";
import { AdminUsersListParams, AdminUsersService } from "./admin-users-service";

const adminUsersService = new AdminUsersService(httpClient);

export const adminUsersKeys = {
  all: ["admin", "users"] as const,
  list: (params: AdminUsersListParams) => ["admin", "users", "list", params] as const,
  detail: (userId: string) => ["admin", "users", "detail", userId] as const,
};

export function useAdminUsersQuery(params: AdminUsersListParams) {
  return useQuery({
    queryKey: adminUsersKeys.list(params),
    queryFn: async () => (await adminUsersService.listUsers(params)).data ?? null,
    placeholderData: (prev) => prev,
  });
}

export function useAdminUserDetailQuery(userId: string | null) {
  return useQuery({
    queryKey: adminUsersKeys.detail(userId ?? ""),
    queryFn: async () => (await adminUsersService.getUserDetail(userId as string)).data ?? null,
    enabled: !!userId,
  });
}

function useInvalidateAdminUsers() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: adminUsersKeys.all });
}

export function useSuspendUserMutation() {
  const invalidate = useInvalidateAdminUsers();
  return useMutation({
    mutationFn: ({ userId, reason }: { userId: string; reason: string }) =>
      adminUsersService.suspendUser(userId, reason),
    onSuccess: invalidate,
  });
}

export function useReactivateUserMutation() {
  const invalidate = useInvalidateAdminUsers();
  return useMutation({
    mutationFn: (userId: string) => adminUsersService.reactivateUser(userId),
    onSuccess: invalidate,
  });
}

export function useForcePasswordResetMutation() {
  return useMutation({
    mutationFn: (userId: string) => adminUsersService.forcePasswordReset(userId),
  });
}

export function useSetTrustStatusMutation() {
  const invalidate = useInvalidateAdminUsers();
  return useMutation({
    mutationFn: ({ userId, trustStatus }: { userId: string; trustStatus: TrustStatus }) =>
      adminUsersService.setTrustStatus(userId, trustStatus),
    onSuccess: invalidate,
  });
}

export { adminUsersService };
