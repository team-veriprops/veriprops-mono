/**
 * Lightweight, privacy-conscious device fingerprint. Stable across reloads
 * for the same browser, derived from non-sensitive surfaces:
 *  - userAgent / platform / language / timezone
 *  - canvas rendering hash (rough proxy for GPU/font stack)
 *  - screen geometry
 *
 * No third-party SDK, no tracking pixel. The result is sent to the backend
 * with login/signup payloads to power fraud-detection heuristics (PRD §2.1).
 */

const STORAGE_KEY = "veriprops-fp-cache";

export function getDeviceFingerprint(): string {
  if (typeof window === "undefined") return "";
  try {
    const cached = localStorage.getItem(STORAGE_KEY);
    if (cached) return cached;
  } catch {
    /* ignore */
  }
  const fp = computeFingerprint();
  try {
    localStorage.setItem(STORAGE_KEY, fp);
  } catch {
    /* ignore */
  }
  return fp;
}

function computeFingerprint(): string {
  const parts: string[] = [];

  if (typeof navigator !== "undefined") {
    parts.push(navigator.userAgent || "");
    parts.push(navigator.language || "");
    parts.push(String(navigator.hardwareConcurrency || 0));
    parts.push((navigator as unknown as { platform?: string }).platform || "");
  }

  if (typeof screen !== "undefined") {
    parts.push(`${screen.width}x${screen.height}x${screen.colorDepth}`);
  }

  try {
    parts.push(Intl.DateTimeFormat().resolvedOptions().timeZone || "");
  } catch {
    /* ignore */
  }

  parts.push(canvasHash());

  return djb2(parts.join("|"));
}

function canvasHash(): string {
  if (typeof document === "undefined") return "";
  try {
    const canvas = document.createElement("canvas");
    canvas.width = 200;
    canvas.height = 50;
    const ctx = canvas.getContext("2d");
    if (!ctx) return "";
    ctx.textBaseline = "top";
    ctx.font = "16px 'Arial'";
    ctx.fillStyle = "#102030";
    ctx.fillRect(0, 0, 200, 50);
    ctx.fillStyle = "#f8f9fa";
    ctx.fillText("veriprops-fp ✓", 4, 4);
    return djb2(canvas.toDataURL().slice(-128));
  } catch {
    return "";
  }
}

function djb2(str: string): string {
  let hash = 5381;
  for (let i = 0; i < str.length; i++) {
    hash = ((hash << 5) + hash + str.charCodeAt(i)) | 0;
  }
  return (hash >>> 0).toString(16).padStart(8, "0");
}
