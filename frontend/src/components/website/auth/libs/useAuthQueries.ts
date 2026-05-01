"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { httpClient } from "@/containers";
import { AuthService } from "./auth-service";
import { useAuthStore } from "@components/website/auth/libs/useAuthStore";
import type {
  ForgotPasswordRequest,
  LoginRequest,
  OtpSendRequest,
  OtpVerifyRequest,
  ProfileCompletionRequest,
  ResetPasswordRequest,
  SetPasswordRequest,
  SignupRequest,
} from "./auth-service";
import { SocialProvider } from "@components/website/auth/models";
const authService = new AuthService(httpClient);

export const authKeys = {
  session: ["auth", "session"] as const,
  devices: ["auth", "devices"] as const,
  events:  ["auth", "security-events"] as const,
  linked:  ["auth", "linked-providers"] as const,
};

export function useCurrentSession(enabled = true) {
  const setSession = useAuthStore((s) => s.setSession);
  return useQuery({
    queryKey: authKeys.session,
    enabled,
    queryFn: async () => {
      const res = await authService.currentSession();
      if (res.data) setSession(res.data);
      return res.data ?? null;
    },
    retry: false,
    staleTime: 60_000,
  });
}

export function useSignupMutation() {
  const setSession = useAuthStore((s) => s.setSession);
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: SignupRequest) => authService.signup(payload),
    onSuccess: (res) => {
      if (res.data) setSession(res.data);
      qc.invalidateQueries({ queryKey: authKeys.session });
    },
  });
}

export function useLoginMutation() {
  const setSession = useAuthStore((s) => s.setSession);
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: LoginRequest) => authService.login(payload),
    onSuccess: (res) => {
      if (res.data) setSession(res.data);
      qc.invalidateQueries({ queryKey: authKeys.session });
    },
  });
}

export function useLogoutMutation() {
  const clear = useAuthStore((s) => s.clear);
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => authService.logout(),
    onSuccess: () => {
      clear();
      qc.removeQueries({ queryKey: authKeys.session });
    },
  });
}

export const useSendOtpMutation = () =>
  useMutation({ mutationFn: (payload: OtpSendRequest) => authService.sendOtp(payload) });

export const useVerifyOtpMutation = () =>
  useMutation({ mutationFn: (payload: OtpVerifyRequest) => authService.verifyOtp(payload) });

export const useForgotPasswordMutation = () =>
  useMutation({ mutationFn: (payload: ForgotPasswordRequest) => authService.forgotPassword(payload) });

export const useResetPasswordMutation = () =>
  useMutation({ mutationFn: (payload: ResetPasswordRequest) => authService.resetPassword(payload) });

export const useSetPasswordMutation = () =>
  useMutation({ mutationFn: (payload: SetPasswordRequest) => authService.setPassword(payload) });

export const useCompleteProfileMutation = () => {
  const setSession = useAuthStore((s) => s.setSession);
  return useMutation({
    mutationFn: (payload: ProfileCompletionRequest) => authService.completeProfile(payload),
    onSuccess: (res) => {
      if (res.data) setSession(res.data);
    },
  });
};

export function useDevicesQuery() {
  return useQuery({
    queryKey: authKeys.devices,
    queryFn: async () => (await authService.listDevices()).data ?? [],
  });
}

export function useRevokeDeviceMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (sessionId: string) => authService.revokeDevice(sessionId),
    onSuccess: () => qc.invalidateQueries({ queryKey: authKeys.devices }),
  });
}

export function useRevokeAllOtherDevicesMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => authService.revokeAllOtherDevices(),
    onSuccess: () => qc.invalidateQueries({ queryKey: authKeys.devices }),
  });
}

export function useSecurityEventsQuery() {
  return useQuery({
    queryKey: authKeys.events,
    queryFn: async () => (await authService.listSecurityEvents()).data ?? [],
  });
}

export function useLinkedProvidersQuery() {
  return useQuery({
    queryKey: authKeys.linked,
    queryFn: async () => (await authService.listLinkedProviders()).data ?? [],
  });
}

export function useUnlinkProviderMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (provider: SocialProvider) => authService.unlinkProvider(provider),
    onSuccess: () => qc.invalidateQueries({ queryKey: authKeys.linked }),
  });
}

export const authConsentKeys = {
  missing: ["auth", "consents", "missing"] as const,
};

export function useMissingConsentsQuery(enabled = true) {
  return useQuery({
    queryKey: authConsentKeys.missing,
    enabled,
    queryFn: async () => (await authService.listMissingConsents()).data?.documents ?? [],
    staleTime: 60_000,
  });
}

export function useAcceptConsentsMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (consents: Array<{ documentType: string; consentVersion: string; acceptedAt: string }>) =>
      authService.acceptConsents(consents),
    onSuccess: () => qc.invalidateQueries({ queryKey: authConsentKeys.missing }),
  });
}

export { authService };
