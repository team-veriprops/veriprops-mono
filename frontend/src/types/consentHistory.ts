// Versioned consent history (PRD §19.1 / R19.4). Mirrors the S57 DTOs in
// app/domain/user/auth/consent/models.py — camelCase on the wire.

export interface UserConsentHistoryItem {
  documentType: string;
  consentVersion: string;
  acceptedAt: string;
  ipAddress?: string | null;
  deviceFingerprint?: string | null;
}

export interface UserConsentHistoryPage {
  items: UserConsentHistoryItem[];
  total: number;
  page: number;
  pageSize: number;
}
