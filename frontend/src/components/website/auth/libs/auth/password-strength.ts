/**
 * Lightweight password strength scorer. Returns a 0–4 band similar to zxcvbn
 * without the dictionary-attack heuristics. Good enough for UX nudges; the
 * authoritative validation happens server-side.
 */
export interface StrengthResult {
  score: 0 | 1 | 2 | 3 | 4;
  label: "Too weak" | "Weak" | "Fair" | "Strong" | "Very strong";
  hints: string[];
}

const COMMON: ReadonlySet<string> = new Set([
  "password", "password1", "qwerty", "111111", "123456", "12345678",
  "123456789", "letmein", "welcome", "iloveyou", "admin", "monkey",
  "abc123", "veriprops", "nigeria", "lagos",
]);

export function scorePassword(password: string): StrengthResult {
  const hints: string[] = [];
  if (!password) return { score: 0, label: "Too weak", hints: ["Enter a password"] };

  const lower = password.toLowerCase();
  if (COMMON.has(lower)) {
    return { score: 0, label: "Too weak", hints: ["This password is too common"] };
  }

  const length = password.length;
  const hasLower = /[a-z]/.test(password);
  const hasUpper = /[A-Z]/.test(password);
  const hasDigit = /\d/.test(password);
  const hasSymbol = /[^A-Za-z0-9]/.test(password);

  let score = 0;
  if (length >= 8) score++;
  if (length >= 12) score++;
  if (hasLower && hasUpper) score++;
  if (hasDigit) score++;
  if (hasSymbol) score++;

  if (length < 8) hints.push("Use at least 8 characters");
  if (!hasUpper) hints.push("Mix in an uppercase letter");
  if (!hasDigit) hints.push("Add a number");
  if (!hasSymbol) hints.push("Add a symbol like ! or #");

  // Repeating characters / sequential digits penalty
  if (/(.)\1{2,}/.test(password)) {
    score = Math.max(0, score - 1);
    hints.push("Avoid repeating characters");
  }
  if (/0123|1234|2345|3456|4567|5678|6789/.test(password)) {
    score = Math.max(0, score - 1);
    hints.push("Avoid sequential digits");
  }

  // Hard cap: anything below the minimum length cannot exceed Weak (1).
  if (length < 8) score = Math.min(score, 1);

  const clamped = Math.max(0, Math.min(4, score)) as 0 | 1 | 2 | 3 | 4;
  const label = (
    ["Too weak", "Weak", "Fair", "Strong", "Very strong"] as const
  )[clamped];
  return { score: clamped, label, hints: hints.slice(0, 2) };
}

export const MIN_PASSWORD_LENGTH = 8;
