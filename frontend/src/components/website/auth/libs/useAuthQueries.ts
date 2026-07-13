"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { DEFAULT_HISTORY_PAGE_SIZE, STALE_TIME_MS, SHORT_STALE_TIME_MS, LONG_STALE_TIME_MS } from "@lib/config/app";
import { httpClient } from "@/containers";
import { isAutomationEnvironment } from "@lib/automation";
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
  events:  (page: number, pageSize: number) => ["auth", "security-events", page, pageSize] as const,
  linked:  ["auth", "linked-providers"] as const,
  crossPortal: ["auth", "cross-portal"] as const,
  publicConfig: ["config", "public"] as const,
};

export function useCurrentSession(enabled = true) {
  const setSession = useAuthStore((s) => s.setSession);
  return useQuery({
    queryKey: authKeys.session,
    enabled,
    queryFn: async () => {
      const res = await authService.currentSession();
      if (res.data) setSession(res.data);
      if (isAutomationEnvironment()) {
        window.__auth_snapshot__ = {
          isAuthenticated: !!res.data,
          userId: res.data?.user?.id ?? null,
          personas: res.data?.user?.personas ?? [],
        };
      }
      return res.data ?? null;
    },
    retry: false,
    staleTime: STALE_TIME_MS,
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

/** Phase-5 phone verification for the logged-in user (§5) — the phone comes from the session. */
export const useSendPhoneOtpMutation = () =>
  useMutation({ mutationFn: () => authService.sendPhoneOtp() });

export const useVerifyPhoneMutation = () =>
  useMutation({ mutationFn: (code: string) => authService.verifyPhone(code) });

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

export function useSecurityEventsQuery(page = 0, pageSize = DEFAULT_HISTORY_PAGE_SIZE) {
  return useQuery({
    queryKey: authKeys.events(page, pageSize),
    queryFn: () => authService.listSecurityEvents(page, pageSize),
    placeholderData: (prev) => prev,
  });
}

export function useCrossPortalSummaryQuery(enabled = true) {
  return useQuery({
    queryKey: authKeys.crossPortal,
    enabled,
    queryFn: async () => (await authService.getCrossPortalSummary()).data ?? null,
    staleTime: SHORT_STALE_TIME_MS,
  });
}

export function usePublicConfigQuery() {
  return useQuery({
    queryKey: authKeys.publicConfig,
    queryFn: async () => (await authService.getPublicConfig()).data ?? null,
    staleTime: LONG_STALE_TIME_MS,
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
  document: (slug: string | null) => ["auth", "consents", "document", slug] as const,
};

export function useMissingConsentsQuery(enabled = true) {
  return useQuery({
    queryKey: authConsentKeys.missing,
    enabled,
    queryFn: async () => (await authService.listMissingConsents()).data?.documents ?? [],
    staleTime: STALE_TIME_MS,
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

// Fetches a legal document's full body for inline viewing (e.g. in the consent
// re-acceptance modal). Disabled until a slug is selected.
export function useLegalDocumentQuery(slug: string | null) {
  return useQuery({
    queryKey: authConsentKeys.document(slug),
    enabled: !!slug,
    queryFn: async () => (await authService.getLegalDocument(slug!)).data ?? null,
    staleTime: LONG_STALE_TIME_MS,
  });
}

export { authService };
