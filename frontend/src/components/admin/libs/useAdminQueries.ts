"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { httpClient } from "@/containers";
import {
  AdminService,
  type AdminInvitationStatus,
  type AdminSubRole,
  type VerificationStatus,
  type VerificationTier,
} from "./admin-service";

export const adminService = new AdminService(httpClient);

export const adminKeys = {
  invitations: (status?: AdminInvitationStatus) =>
    ["admin", "invitations", status ?? "all"] as const,
  applications: (status?: "PENDING" | "APPROVED" | "REJECTED") =>
    ["admin", "agent-applications", status ?? "all"] as const,
  verifications: (opts?: Record<string, string>) =>
    ["admin", "verifications", opts ?? {}] as const,
  verificationDetail: (vid: string) =>
    ["admin", "verifications", vid] as const,
  tasks: (vid: string) =>
    ["admin", "verifications", vid, "tasks"] as const,
  availableAgents: (opts?: { role?: string; state?: string }) =>
    ["admin", "available-agents", opts ?? {}] as const,
  config: () =>
    ["admin", "config"] as const,
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

// ── Admin verifications ──

export function useAdminVerifications(opts?: {
  status?: string;
  tier?: string;
  state?: string;
  lga?: string;
  vid?: string;
  page?: number;
}) {
  return useQuery({
    queryKey: adminKeys.verifications(opts as Record<string, string>),
    queryFn: () => adminService.listVerifications(opts),
    staleTime: 15_000,
  });
}

export function useAdminVerificationDetail(vid: string) {
  return useQuery({
    queryKey: adminKeys.verificationDetail(vid),
    queryFn: () => adminService.getVerification(vid),
    staleTime: 15_000,
  });
}

export function usePauseVerificationMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vid: string) => adminService.pauseVerification(vid),
    onSuccess: (_data, vid) => {
      qc.invalidateQueries({ queryKey: adminKeys.verificationDetail(vid) });
      qc.invalidateQueries({ queryKey: ["admin", "verifications"] });
    },
  });
}

export function useResumeVerificationMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vid: string) => adminService.resumeVerification(vid),
    onSuccess: (_data, vid) => {
      qc.invalidateQueries({ queryKey: adminKeys.verificationDetail(vid) });
      qc.invalidateQueries({ queryKey: ["admin", "verifications"] });
    },
  });
}

export function useCancelVerificationMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vid: string) => adminService.cancelVerification(vid),
    onSuccess: (_data, vid) => {
      qc.invalidateQueries({ queryKey: adminKeys.verificationDetail(vid) });
      qc.invalidateQueries({ queryKey: ["admin", "verifications"] });
    },
  });
}

export function useFailVerificationMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ vid, reason }: { vid: string; reason: string }) =>
      adminService.failVerification(vid, reason),
    onSuccess: (_data, { vid }) => {
      qc.invalidateQueries({ queryKey: adminKeys.verificationDetail(vid) });
      qc.invalidateQueries({ queryKey: ["admin", "verifications"] });
    },
  });
}

export function useAddNoteMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      vid,
      content,
      tags,
      pinned,
    }: {
      vid: string;
      content: string;
      tags: string[];
      pinned: boolean;
    }) => adminService.addNote(vid, { content, tags, pinned }),
    onSuccess: (_data, { vid }) =>
      qc.invalidateQueries({ queryKey: adminKeys.verificationDetail(vid) }),
  });
}

export function useReleaseToPoolMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vid: string) => adminService.releaseToPool(vid),
    onSuccess: (_data, vid) =>
      qc.invalidateQueries({ queryKey: adminKeys.verificationDetail(vid) }),
  });
}

// ── Admin tasks ──

export function useVerificationTasks(vid: string) {
  return useQuery({
    queryKey: adminKeys.tasks(vid),
    queryFn: () => adminService.listTasksForVerification(vid),
    staleTime: 15_000,
  });
}

export function useAvailableAgents(opts?: { role?: string; state?: string }) {
  return useQuery({
    queryKey: adminKeys.availableAgents(opts),
    queryFn: () => adminService.listAvailableAgents(opts),
    staleTime: 30_000,
  });
}

export function useAssignTaskMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ vid, role, agentId }: { vid: string; role: string; agentId: string }) =>
      adminService.assignTask(vid, role, agentId),
    onSuccess: (_data, { vid }) =>
      qc.invalidateQueries({ queryKey: adminKeys.tasks(vid) }),
  });
}

export function useReassignTaskMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      taskId,
      agentId,
      note,
      vid,
    }: {
      taskId: string;
      agentId: string;
      note?: string;
      vid: string;
    }) => adminService.reassignTask(taskId, agentId, note),
    onSuccess: (_data, { vid }) =>
      qc.invalidateQueries({ queryKey: adminKeys.tasks(vid) }),
  });
}

// ── Admin config ──

export function useAdminConfig() {
  return useQuery({
    queryKey: adminKeys.config(),
    queryFn: () => adminService.listConfig(),
    staleTime: 60_000,
  });
}

export function useSetConfigMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ key, value }: { key: string; value: string }) =>
      adminService.setConfig(key, value),
    onSuccess: () => qc.invalidateQueries({ queryKey: adminKeys.config() }),
  });
}
