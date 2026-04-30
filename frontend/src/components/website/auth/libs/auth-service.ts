import { HttpClient } from "@lib/FetchHttpClient";
import { SuccessResponse } from "@/types/models";
import { AuthSession, DeviceSession, OtpChannel, SecurityEvent, SignupDraft, SocialProvider, UserConsent } from "@components/website/auth/models";
/**
 * Frontend-facing auth API. Endpoint paths follow the convention used elsewhere
 * in the app (`/users/auth/...` — see FetchHttpClient.refreshToken). Backend is
 * not yet implemented; the frontend ships this client now so wiring is identical
 * once Phase 2 backend ships. Until then, callers should expect rejected promises
 * in dev — components handle this gracefully.
 */

export interface SignupRequest {
  firstName: string;
  lastName: string;
  email: string;
  password: string;
  countryCode: string;
  dialCode: string;
  phone: string;
  countryOfResidence: string;
  timezone: string;
  preferredCurrency: string;
  consents: UserConsent[];
  intent?: string;
  deviceFingerprint?: string;
}

export interface LoginRequest {
  email: string;
  password: string;
  deviceFingerprint?: string;
}

export interface OtpSendRequest {
  channel: OtpChannel;
  email?: string;
  countryCode?: string;
  dialCode?: string;
  phone?: string;
}

export interface OtpVerifyRequest extends OtpSendRequest {
  code: string;
}

export interface ForgotPasswordRequest {
  email: string;
}

export interface ResetPasswordRequest {
  token: string;
  password: string;
}

export interface SetPasswordRequest {
  password: string;
}

export interface ProfileCompletionRequest {
  countryCode: string;
  dialCode: string;
  phone: string;
  countryOfResidence: string;
  timezone: string;
  preferredCurrency: string;
}

export class AuthService {
  private readonly base = "/users/auth";

  constructor(private readonly http: HttpClient) {}

  signup(payload: SignupRequest): Promise<SuccessResponse<AuthSession>> {
    return this.http.post(`${this.base}/signup`, payload);
  }

  login(payload: LoginRequest): Promise<SuccessResponse<AuthSession>> {
    return this.http.post(`${this.base}/sessions`, payload);
  }

  logout(): Promise<SuccessResponse<null>> {
    return this.http.delete(`${this.base}/sessions/current`);
  }

  currentSession(): Promise<SuccessResponse<AuthSession>> {
    return this.http.get(`${this.base}/sessions/current`);
  }

  sendOtp(payload: OtpSendRequest): Promise<SuccessResponse<{ resendIn: number }>> {
    return this.http.post(`${this.base}/otp/send`, payload);
  }

  verifyOtp(payload: OtpVerifyRequest): Promise<SuccessResponse<{ verified: true }>> {
    return this.http.post(`${this.base}/otp/verify`, payload);
  }

  forgotPassword(payload: ForgotPasswordRequest): Promise<SuccessResponse<null>> {
    return this.http.post(`${this.base}/password/forgot`, payload);
  }

  resetPassword(payload: ResetPasswordRequest): Promise<SuccessResponse<null>> {
    return this.http.post(`${this.base}/password/reset`, payload);
  }

  setPassword(payload: SetPasswordRequest): Promise<SuccessResponse<null>> {
    return this.http.post(`${this.base}/password/set`, payload);
  }

  startOauth(provider: SocialProvider, intent?: string): string {
    const search = new URLSearchParams();
    if (intent) search.set("intent", intent);
    const qs = search.toString();
    return `/api${this.base}/oauth/${provider}/start${qs ? `?${qs}` : ""}`;
  }

  completeProfile(payload: ProfileCompletionRequest): Promise<SuccessResponse<AuthSession>> {
    return this.http.post(`${this.base}/profile/complete`, payload);
  }

  listDevices(): Promise<SuccessResponse<DeviceSession[]>> {
    return this.http.get(`${this.base}/sessions`);
  }

  revokeDevice(sessionId: string): Promise<SuccessResponse<null>> {
    return this.http.delete(`${this.base}/sessions/${sessionId}`);
  }

  revokeAllOtherDevices(): Promise<SuccessResponse<null>> {
    return this.http.delete(`${this.base}/sessions?scope=others`);
  }

  listSecurityEvents(): Promise<SuccessResponse<SecurityEvent[]>> {
    return this.http.get(`${this.base}/sessions/security/events`);
  }

  listLinkedProviders(): Promise<SuccessResponse<SocialProvider[]>> {
    return this.http.get(`${this.base}/oauth/links`);
  }

  /**
   * Confirms a pending OAuth link after the user has signed in with the
   * password account that owns the colliding email. Backend looks up the
   * cached pending profile keyed on `(user_id, provider)`.
   */
  linkPendingOauth(provider: SocialProvider): Promise<SuccessResponse<null>> {
    return this.http.post(`${this.base}/oauth/links/link`, { provider });
  }

  unlinkProvider(provider: SocialProvider): Promise<SuccessResponse<null>> {
    return this.http.delete(`${this.base}/oauth/links/${provider}`);
  }

  // ── Consent re-acceptance ────────────────────────────────────────
  listMissingConsents(): Promise<SuccessResponse<{ documents: Array<{
    type: string; consentVersion: string; effectiveAt: string; title: string; href: string;
  }> }>> {
    return this.http.get(`${this.base}/consents/missing`);
  }

  acceptConsents(consents: Array<{
    documentType: string; consentVersion: string; acceptedAt: string;
  }>): Promise<SuccessResponse<null>> {
    return this.http.post(`${this.base}/consents/accept`, { consents });
  }

  // ── Resumable signup draft (server-side keyed on email) ─────────
  saveSignupDraft(payload: SignupDraft): Promise<SuccessResponse<null>> {
    return this.http.put(`${this.base}/signup/draft`, payload);
  }

  getSignupDraft(email: string): Promise<SuccessResponse<SignupDraft | null>> {
    const qs = new URLSearchParams({ email }).toString();
    return this.http.get(`${this.base}/signup/draft?${qs}`);
  }

  discardSignupDraft(email: string): Promise<SuccessResponse<null>> {
    const qs = new URLSearchParams({ email }).toString();
    return this.http.delete(`${this.base}/signup/draft?${qs}`);
  }
}
