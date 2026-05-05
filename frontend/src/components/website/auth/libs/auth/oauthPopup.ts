/**
 * Popup-based OAuth orchestrator.
 *
 * Flow:
 * 1. User clicks the social button — synchronously open a blank popup so the
 *    browser does not flag the action as automated.
 * 2. Fetch `/api/users/auth/oauth/{provider}/start` to get the authorizationUrl.
 * 3. Navigate the popup to the provider.
 * 4. Listen for `postMessage({ type: "oauth_result", success, message? })`
 *    from the backend's callback page (same origin as our window).
 * 5. Resolve via `onSuccess` / `onError`. If the popup closes before a message
 *    arrives, treat as cancellation. Hard timeout after 5 minutes.
 *
 * Security: validate `event.origin === window.location.origin` and
 * `event.data.type === "oauth_result"` before acting on a message. Anything
 * else is silently dropped.
 */

import { isAutomationEnvironment } from "@lib/automation";
import { authService } from "@components/website/auth/libs/useAuthQueries";
import { OAuthFlowMode, SocialProvider } from "@components/website/auth/models";

export interface OauthPopupOptions {
  intent?: string;
  mode?: OAuthFlowMode;
  /** Total wait time before forcing failure. Default: 5 minutes. */
  timeoutMs?: number;
  /** Closed-poll interval (ms). Default: 500ms. */
  pollIntervalMs?: number;
  onSuccess: () => void;
  /** User closed the popup without finishing. No toast / log spam. */
  onCancel?: () => void;
  /** Provider or backend reported failure. `code === "popup_blocked"` on a
   * blocked popup so the caller can offer a fallback redirect. */
  onError: (err: { code: "popup_blocked" | "timeout" | "provider"; message?: string; authorizationUrl?: string }) => void;
}

const DEFAULT_TIMEOUT_MS = 5 * 60 * 1000;
const DEFAULT_POLL_MS = 500;
const POPUP_NAME = "veriprops_oauth";

function signalOauthComplete(status: "success" | "failed"): void {
  if (!isAutomationEnvironment()) return;
  (window as any).__oauth_complete__ = status;
  window.dispatchEvent(new CustomEvent("__oauth_complete__", { detail: { status } }));
}

export function startOauthPopup(provider: SocialProvider, opts: OauthPopupOptions): { cancel: () => void } {
  const {
    intent,
    mode,
    timeoutMs = DEFAULT_TIMEOUT_MS,
    pollIntervalMs = DEFAULT_POLL_MS,
    onSuccess,
    onCancel,
    onError,
  } = opts;

  if (isAutomationEnvironment()) {
    (window as any).__oauth_complete__ = null;
  }

  // Synchronously open the popup. Browsers count this as a direct response to
  // the user gesture; deferring until after the fetch trips popup-blockers.
  const features = popupFeatures(520, 620);
  const popup = window.open("about:blank", POPUP_NAME, features);

  let resolved = false;
  let timeoutId: ReturnType<typeof setTimeout> | null = null;
  let closedPollId: ReturnType<typeof setInterval> | null = null;
  let lastAuthorizationUrl: string | undefined;

  const cleanup = () => {
    window.removeEventListener("message", onMessage);
    if (timeoutId !== null) clearTimeout(timeoutId);
    if (closedPollId !== null) clearInterval(closedPollId);
    if (popup && !popup.closed) {
      try { popup.close(); } catch { /* ignore */ }
    }
  };

  const onMessage = (event: MessageEvent) => {
    if (resolved) return;
    if (event.origin !== window.location.origin) return;
    const data = event.data as unknown;
    if (!isOauthResult(data)) return;
    resolved = true;
    cleanup();
    if (data.success) {
      signalOauthComplete("success");
      onSuccess();
    } else {
      signalOauthComplete("failed");
      onError({ code: "provider", message: data.message ?? undefined, authorizationUrl: lastAuthorizationUrl });
    }
  };

  const cancel = () => {
    if (resolved) return;
    resolved = true;
    cleanup();
    signalOauthComplete("failed");
    onCancel?.();
  };

  if (!popup) {
    // Popup blocked — surface so caller can offer fallback redirect. We still
    // fetch the authorizationUrl so the fallback can use it directly.
    authService.startOauth(provider, { intent, mode })
      .then((res) => {
        signalOauthComplete("failed");
        onError({ code: "popup_blocked", authorizationUrl: res.data?.authorizationUrl });
      })
      .catch(() => {
        signalOauthComplete("failed");
        onError({ code: "popup_blocked" });
      });
    return { cancel: () => undefined };
  }

  window.addEventListener("message", onMessage);

  closedPollId = setInterval(() => {
    if (popup.closed && !resolved) {
      cancel();
    }
  }, pollIntervalMs);

  timeoutId = setTimeout(() => {
    if (resolved) return;
    resolved = true;
    cleanup();
    signalOauthComplete("failed");
    onError({ code: "timeout" });
  }, timeoutMs);

  authService.startOauth(provider, { intent, mode })
    .then((res) => {
      if (resolved) return;
      const url = res.data?.authorizationUrl;
      if (!url) {
        resolved = true;
        cleanup();
        signalOauthComplete("failed");
        onError({ code: "provider", message: "OAuth start did not return an authorization URL." });
        return;
      }
      lastAuthorizationUrl = url;
      try {
        popup.location.href = url;
      } catch {
        // Some browsers throw if the popup was already navigated away.
        if (!resolved) {
          resolved = true;
          cleanup();
          signalOauthComplete("failed");
          onError({ code: "provider", message: "Could not navigate the popup window." });
        }
      }
    })
    .catch((err) => {
      if (resolved) return;
      resolved = true;
      window.removeEventListener("message", onMessage);
      if (timeoutId !== null) clearTimeout(timeoutId);
      if (closedPollId !== null) clearInterval(closedPollId);
      try {
        if (popup && !popup.closed) {
          popup.location.href = `${window.location.origin}/auth/oauth/error`;
        }
      } catch { /* ignore */ }
      signalOauthComplete("failed");
      onError({ code: "provider", message: err?.message });
    });

  return { cancel };
}

function popupFeatures(width: number, height: number): string {
  if (typeof window === "undefined") return "";
  const left = Math.max(0, Math.round((window.outerWidth - width) / 2 + (window.screenX ?? 0)));
  const top = Math.max(0, Math.round((window.outerHeight - height) / 2 + (window.screenY ?? 0)));
  return `popup=yes,width=${width},height=${height},left=${left},top=${top},scrollbars=yes,resizable=yes,noopener=no,noreferrer=no`;
}

function isOauthResult(data: unknown): data is { type: "oauth_result"; success: boolean; message?: string } {
  if (!data || typeof data !== "object") return false;
  const d = data as Record<string, unknown>;
  return d.type === "oauth_result" && typeof d.success === "boolean";
}
