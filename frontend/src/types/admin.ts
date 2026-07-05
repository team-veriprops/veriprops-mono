// Admin onboarding & RBAC types — mirror backend camelCase DTOs (PRD §4.1).

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

export interface InvitePreview {
  email: string;
  firstName?: string;
  lastName?: string;
  subRole: AdminSubRole;
  status: AdminInvitationStatus;
  expired: boolean;
  scenario: InviteAcceptScenario;
}
