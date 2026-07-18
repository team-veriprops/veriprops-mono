// Admin onboarding & RBAC types — mirror backend camelCase DTOs (PRD §4.1).

import {
  AccountStatus,
  SecurityEvent,
  TrustStatus,
  UserPersona,
  UserType,
} from "@components/website/auth/models";

export enum AdminSubRole {
  SUPER = "SUPER",
  OPERATIONS = "OPERATIONS",
  FINANCE = "FINANCE",
  CONTENT_CREATOR = "CONTENT_CREATOR",
  CONTENT_APPROVER = "CONTENT_APPROVER",
}

export enum AdminInvitationStatus {
  PENDING = "PENDING",
  ACCEPTED = "ACCEPTED",
  REVOKED = "REVOKED",
}

export enum InviteAcceptScenario {
  NEW_USER = "NEW_USER",
  EXISTING_USER = "EXISTING_USER",
  ALREADY_ADMIN = "ALREADY_ADMIN",
}

export interface AdminMember {
  id: string;
  name: string;
  email: string;
  subRole?: AdminSubRole;
  active: boolean;
  dateCreated: string;
}

export interface AdminTeamPage {
  items: AdminMember[];
  total: number;
  page: number;
  pageSize: number;
}

export interface AdminInvitationSummary {
  id: string;
  email: string;
  firstName?: string;
  lastName?: string;
  subRole: AdminSubRole;
  status: AdminInvitationStatus;
  invitedBy: string;
  expiresAt: string;
  dateCreated: string;
}

// ── Admin user management (PRD §4.2) — mirrors backend admin_users/models.py ──

export interface AdminUserSummary {
  id: string;
  name: string;
  email: string;
  emailVerified: boolean;
  phone: string;
  phoneDialCode: string;
  userType: UserType;
  personas: UserPersona[];
  adminSubRole?: AdminSubRole;
  trustStatus: TrustStatus;
  accountStatus: AccountStatus;
  avatarUrl?: string;
  dateCreated: string;
}

export interface AdminUserDetail extends AdminUserSummary {
  firstName: string;
  lastName: string;
  phoneCountryCode: string;
  phoneVerified: boolean;
  countryOfResidence: string;
  timezone: string;
  preferredCurrency: string;
  creditBalanceKobo: number;
  referredBy?: string;
  lockedUntil?: string;
  suspendedAt?: string;
  suspensionReason?: string;
  suspendedBy?: string;
  verificationCounts: Record<string, number>;
  verificationsTotal: number;
  paymentsCount: number;
  recentSecurityEvents: SecurityEvent[];
}

export interface InvitePreview {
  email: string;
  firstName?: string;
  lastName?: string;
  subRole: AdminSubRole;
  status: AdminInvitationStatus;
  expired: boolean;
  scenario: InviteAcceptScenario;
}
