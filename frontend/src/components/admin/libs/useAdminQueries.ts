"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { httpClient } from "@/containers";
import {
  AdminService,
  type AdminInvitationStatus,
  type AdminSubRole,
} from "./admin-service";

export const adminService = new AdminService(httpClient);

export const adminKeys = {
  invitations: (status?: AdminInvitationStatus) =>
    ["admin", "invitations", status ?? "all"] as const,
  applications: (status?: "PENDING" | "APPROVED" | "REJECTED") =>
    ["admin", "agent-applications", status ?? "all"] as const,
};

// ── Invitations ──

export function useAdminInvitations(status?: AdminInvitationStatus) {
  return useQuery({
    queryKey: adminKeys.invitations(status),
    queryFn: () => adminService.listInvitations(status),
    staleTime: 30_000,
  });
}

export function useInviteAdminMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { email: string; subRole: AdminSubRole }) =>
      adminService.inviteAdmin(payload),
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

export function useAcceptInvitationMutation() {
  return useMutation({
    mutationFn: (token: string) => adminService.acceptInvitation(token),
  });
}

// ── Agent applications ──

export function useAgentApplications(status?: "PENDING" | "APPROVED" | "REJECTED") {
  return useQuery({
    queryKey: adminKeys.applications(status),
    queryFn: () => adminService.listAgentApplications({ status }),
    staleTime: 30_000,
  });
}

export function useApproveApplicationMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => adminService.approveApplication(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "agent-applications"] }),
  });
}

export function useRejectApplicationMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      adminService.rejectApplication(id, reason),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "agent-applications"] }),
  });
}
