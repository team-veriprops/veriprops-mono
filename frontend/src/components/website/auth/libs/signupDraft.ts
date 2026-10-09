/**
 * Same-device resume for a half-finished signup, kept in localStorage only.
 *
 * The draft holds what the user typed that is safe to leave in the browser — names, email,
 * phone and residence — and nothing else: never the password, and never the email/phone
 * "verified" flags, since the server's OTP proof expires long before a draft would, so a
 * resumed signup always re-verifies. Every read and write passes through an allowlist, and a
 * stored draft carrying anything outside it (a legacy draft that held the password) is
 * rewritten on read, purging it from the browser.
 */

import { TransactionCurrency } from "@/types/models";

/** The wizard answers a draft may carry. */
export interface SignupDraftFields {
  firstName?: string;
  lastName?: string;
  email?: string;
  countryCode?: string;
  dialCode?: string;
  phone?: string;
  countryOfResidence?: string;
  timezone?: string;
  preferredCurrency?: TransactionCurrency;
}

export interface SignupDraft {
  email: string;
  fields: SignupDraftFields;
  dateUpdated: string;
}

const DRAFT_FIELDS: readonly (keyof SignupDraftFields)[] = [
  "firstName",
  "lastName",
  "email",
  "countryCode",
  "dialCode",
  "phone",
  "countryOfResidence",
  "timezone",
  "preferredCurrency",
];

const KEY_PREFIX = "veriprops-signup-draft:";
const KEY = (email: string) => `${KEY_PREFIX}${email.toLowerCase()}`;
const ACTIVE_KEY = `${KEY_PREFIX}active-email`;

/** Keeps only the allowlisted string fields of `source`. */
const pickDraftFields = (source: unknown): SignupDraftFields => {
  const fields: SignupDraftFields = {};
  if (!source || typeof source !== "object") return fields;
  const record = source as Record<string, unknown>;
  for (const name of DRAFT_FIELDS) {
    const value = record[name];
    if (typeof value === "string") (fields as Record<string, string>)[name] = value;
  }
  // A currency outside the enum (an edited or stale draft) is dropped, not trusted.
  const currencies: readonly string[] = Object.values(TransactionCurrency);
  if (fields.preferredCurrency && !currencies.includes(fields.preferredCurrency)) {
    delete fields.preferredCurrency;
  }
  return fields;
};

/** Builds a clean draft from whatever is stored, reading a legacy `payload` too. */
const toDraft = (stored: unknown): SignupDraft | null => {
  if (!stored || typeof stored !== "object") return null;
  const record = stored as Record<string, unknown>;
  if (typeof record.email !== "string" || !record.email) return null;
  return {
    email: record.email,
    fields: pickDraftFields(record.fields ?? record.payload),
    dateUpdated: typeof record.dateUpdated === "string" ? record.dateUpdated : new Date().toISOString(),
  };
};

export const saveLocalDraft = (email: string, fields: SignupDraftFields) => {
  if (typeof window === "undefined" || !email) return;
  const draft: SignupDraft = {
    email,
    fields: pickDraftFields(fields),
    dateUpdated: new Date().toISOString(),
  };
  try {
    localStorage.setItem(KEY(email), JSON.stringify(draft));
    localStorage.setItem(ACTIVE_KEY, email.toLowerCase());
  } catch {
    /* quota or disabled — silently ignore */
  }
};

export const loadLocalDraft = (email: string): SignupDraft | null => {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(KEY(email));
    if (!raw) return null;
    const draft = toDraft(JSON.parse(raw));
    if (!draft) {
      localStorage.removeItem(KEY(email));
      return null;
    }
    const clean = JSON.stringify(draft);
    if (clean !== raw) localStorage.setItem(KEY(email), clean);
    return draft;
  } catch {
    return null;
  }
};

/** Rewrites every stored draft through the allowlist, not just the active one. */
const sanitizeAllLocalDrafts = () => {
  const emails: string[] = [];
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i);
    if (key?.startsWith(KEY_PREFIX) && key !== ACTIVE_KEY) emails.push(key.slice(KEY_PREFIX.length));
  }
  emails.forEach((email) => loadLocalDraft(email));
};

export const loadActiveLocalDraft = (): SignupDraft | null => {
  if (typeof window === "undefined") return null;
  try {
    sanitizeAllLocalDrafts();
    const email = localStorage.getItem(ACTIVE_KEY);
    return email ? loadLocalDraft(email) : null;
  } catch {
    return null;
  }
};

export const clearLocalDraft = (email: string) => {
  if (typeof window === "undefined") return;
  try {
    localStorage.removeItem(KEY(email));
    const active = localStorage.getItem(ACTIVE_KEY);
    if (active === email.toLowerCase()) localStorage.removeItem(ACTIVE_KEY);
  } catch {
    /* noop */
  }
};
