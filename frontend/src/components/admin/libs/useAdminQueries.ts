"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { httpClient } from "@/containers";
import { AdminService } from "./admin-service";
import { AdminSubRole } from "@/types/admin";

const adminService = new AdminService(httpClient);

export const adminKeys = {
  team: (page: number, pageSize: number) => ["admin", "team", page, pageSize] as const,
  invitations: (page: number, pageSize: number) => ["admin", "invitations", page, pageSize] as const,
  invitePreview: (token: string) => ["admin", "invite-preview", token] as const,
};

export function useAdminTeamQuery(page = 0, pageSize = 10) {
  return useQuery({
    queryKey: adminKeys.team(page, pageSize),
    queryFn: async () => (await adminService.listTeam(page, pageSize)).data ?? null,
    placeholderData: (prev) => prev,
  });
}

export function useAdminInvitationsQuery(page = 0, pageSize = 10) {
  return useQuery({
    queryKey: adminKeys.invitations(page, pageSize),
    queryFn: () => adminService.listInvitations(page, pageSize),
    placeholderData: (prev) => prev,
  });
}

export function useInviteAdminMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ email, subRole }: { email: string; subRole: AdminSubRole }) =>
      adminService.inviteAdmin(email, subRole),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "invitations"] }),
  });
}

export function useRevokeInvitationMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => adminService.revokeInvitation(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "invitations"] }),
  });
}

export function useChangeSubRoleMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, subRole }: { userId: string; subRole: AdminSubRole }) =>
      adminService.changeSubRole(userId, subRole),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "team"] }),
  });
}

export function useDeactivateMemberMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (userId: string) => adminService.deactivateMember(userId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "team"] }),
  });
}

export function useInvitePreviewQuery(token: string) {
  return useQuery({
    queryKey: adminKeys.invitePreview(token),
    queryFn: async () => (await adminService.previewInvitation(token)).data ?? null,
    retry: false,
  });
}

export function useAcceptInvitationMutation() {
  return useMutation({
    mutationFn: (token: string) => adminService.acceptInvitation(token),
  });
}

export { adminService };
