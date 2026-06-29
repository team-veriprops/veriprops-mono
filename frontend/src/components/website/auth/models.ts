// ─────────────────────────────────────────────────────────────────
// Auth & Onboarding domain models (Phase 2)
// PRD §2 (Actors & Role Architecture) and Phase 2 detailed spec.
// All auth-related types live here — observe DDD: types live next to the
// domain that owns them, never in a top-level types/ bag.
// ─────────────────────────────────────────────────────────────────

import { TransactionCurrency } from "@/types/models";

export interface JwtPayload {
  sub?: string
  email?: string
  exp?: number
  iat?: number
  role?: string
  user_type: UserType
  personas: UserPersona[];
}

export enum UserType {
  USER = "USER",
  ADMIN = "ADMIN",
}

export enum AuthIntent {
  DEFAULT = "default", // Customer
  VERIFY = "verify",   // Customer
  AGENT = "agent",     // Agent
  INVITED_ADMIN = "invited-admin", // Admin
}

export enum UserPersona {
  CUSTOMER = "CUSTOMER",
  AGENT = "AGENT",
}

export enum AdminSubRole {
  SUPER = "SUPER",
  OPERATIONS = "OPERATIONS",
  FINANCE = "FINANCE",
}

export enum TrustStatus {
  UNTRUSTED = "UNTRUSTED",
  TRUSTED = "TRUSTED",
}

export enum OtpChannel {
  EMAIL = "EMAIL",
  PHONE = "PHONE",
}

export enum SocialProvider {
  GOOGLE = "google",
  APPLE = "apple",
  FACEBOOK = "facebook",
}

export enum OAuthFlowMode {
  AUTH = "auth",
  LINK = "link",
}

/** @deprecated Use {@link SocialProvider}. Retained for backward compat. */
export const SocialAuthProvider = SocialProvider;
export type SocialAuthProvider = SocialProvider;

export interface AuthUser {
  id: string;
  firstName: string;
  lastName: string;
  email: string;
  emailVerified: boolean;
  phone: string;
  phoneCountryCode: string;
  phoneDialCode: string;
  phoneVerified: boolean;
  countryOfResidence: string;
  timezone: string;
  preferredCurrency: TransactionCurrency;
  userType: UserType;
  personas: UserPersona[];
  adminSubRole?: AdminSubRole;
  trustStatus: TrustStatus;
  hasPassword: boolean;
  linkedProviders: SocialProvider[];
  avatarUrl?: string;
  dateCreated: string;
}

export interface AuthSession {
  accessTokenExpiresAt: string; // ISO timestamp; access token itself is httpOnly cookie
  refreshTokenExpiresAt: string;
  user: AuthUser;
}

export interface DeviceSession {
  id: string;
  device: string;
  browser: string;
  os: string;
  ipAddress: string;
  approxLocation: string;
  current: boolean;
  lastActiveAt: string;
  dateCreated: string;
}

export enum SecurityEventType {
  LOGIN_SUCCESS = "LOGIN_SUCCESS",
  LOGIN_FAILURE = "LOGIN_FAILURE",
  LOGIN_FAILURE_WARNING = "LOGIN_FAILURE_WARNING",
  OTP_SENT = "OTP_SENT",
  OTP_FAILURE = "OTP_FAILURE",
  PASSWORD_CHANGED = "PASSWORD_CHANGED",
  PASSWORD_RESET_REQUESTED = "PASSWORD_RESET_REQUESTED",
  ACCOUNT_LOCKED = "ACCOUNT_LOCKED",
  SESSION_REVOKED = "SESSION_REVOKED",
  OAUTH_LINKED = "OAUTH_LINKED",
  OAUTH_UNLINKED = "OAUTH_UNLINKED",
}

export interface SecurityEvent {
  id: string;
  type: SecurityEventType;
  description: string;
  ipAddress: string;
  approxLocation?: string;
  device?: string;
  occurredAt: string;
}

// Cross-portal awareness (PRD §2.14) — per-persona actionable counts; the
// frontend derives the "other hat" badge from these.
export interface PersonaActionableCount {
  persona: UserPersona;
  actionableCount: number;
}

export interface CrossPortalSummary {
  personas: PersonaActionableCount[];
}

// The full enum lives in @/types/models; re-exported so consent flows can keep
// importing it from here.
export { ConsentDocumentType } from "@/types/models";
import { ConsentDocumentType } from "@/types/models";

export interface ConsentDocument {
  type: ConsentDocumentType;
  consentVersion: string;            // semver, e.g. "1.0.0"
  effectiveAt: string;        // ISO date
  title: string;
  href: string;
}

export interface UserConsent {
  documentType: ConsentDocumentType;
  consentVersion: string;
  acceptedAt: string;
  ipAddress?: string;
  deviceFingerprint?: string;
}

export interface SignupDraft {
  email: string;
  step: number;
  payload: Record<string, unknown>;
  dateUpdated: string;
}
