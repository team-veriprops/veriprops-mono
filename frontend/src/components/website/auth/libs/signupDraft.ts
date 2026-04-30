import { SignupDraft } from "@components/website/auth/models";
/**
 * Local mirror of signup draft state. Backed by localStorage so a tab refresh
 * resumes mid-wizard without a roundtrip. Backend-side draft (server-keyed on
 * email) is the source of truth for cross-device resume — see
 * `AuthService.saveSignupDraft`.
 */

const KEY = (email: string) => `veriprops-signup-draft:${email.toLowerCase()}`;
const ACTIVE_KEY = "veriprops-signup-draft:active-email";

export const saveLocalDraft = (draft: SignupDraft) => {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(KEY(draft.email), JSON.stringify(draft));
    localStorage.setItem(ACTIVE_KEY, draft.email.toLowerCase());
  } catch {
    /* quota or disabled — silently ignore */
  }
};

export const loadLocalDraft = (email: string): SignupDraft | null => {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(KEY(email));
    return raw ? (JSON.parse(raw) as SignupDraft) : null;
  } catch {
    return null;
  }
};

export const loadActiveLocalDraft = (): SignupDraft | null => {
  if (typeof window === "undefined") return null;
  try {
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
