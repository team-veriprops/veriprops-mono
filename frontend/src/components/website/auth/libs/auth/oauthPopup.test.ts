import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { startOauthPopup } from "./oauthPopup";
import { OAuthFlowMode, SocialProvider } from "@components/website/auth/models";

// ── Mock authService ──────────────────────────────────────────────────────────
const { mockStartOauth } = vi.hoisted(() => ({ mockStartOauth: vi.fn() }));
vi.mock("@components/website/auth/libs/useAuthQueries", () => ({
  authService: { startOauth: mockStartOauth },
}));

// Flush pending promise chains without advancing fake timers.
const flushMicrotasks = async () => {
  for (let i = 0; i < 10; i++) await Promise.resolve();
};

// ── Popup stub helpers ────────────────────────────────────────────────────────
function makePopup(closed = false) {
  return {
    closed,
    location: { href: "" },
    close: vi.fn(),
  };
}

function resolvedOauth(url = "https://accounts.google.com/o/oauth2?state=x") {
  return Promise.resolve({ data: { authorizationUrl: url } });
}

beforeEach(() => {
  vi.useFakeTimers();
  mockStartOauth.mockReset();
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

// ── popup_blocked ─────────────────────────────────────────────────────────────
describe("popup_blocked", () => {
  it("calls onError with code=popup_blocked and the authorizationUrl when window.open returns null", async () => {
    vi.spyOn(window, "open").mockReturnValue(null);
    const authorizationUrl = "https://accounts.google.com/o/oauth2?state=y";
    mockStartOauth.mockResolvedValueOnce({ data: { authorizationUrl } });

    const onError = vi.fn();
    startOauthPopup(SocialProvider.GOOGLE, { onSuccess: vi.fn(), onError });

    await vi.runAllTimersAsync();

    expect(onError).toHaveBeenCalledWith({ code: "popup_blocked", authorizationUrl });
  });

  it("calls onError with code=popup_blocked (no URL) when the /start fetch fails", async () => {
    vi.spyOn(window, "open").mockReturnValue(null);
    mockStartOauth.mockRejectedValueOnce(new Error("network error"));

    const onError = vi.fn();
    startOauthPopup(SocialProvider.GOOGLE, { onSuccess: vi.fn(), onError });

    await vi.runAllTimersAsync();

    expect(onError).toHaveBeenCalledWith({ code: "popup_blocked" });
  });
});

// ── cancel (popup closed before message) ─────────────────────────────────────
describe("cancel on close", () => {
  it("calls onCancel when the popup is closed before postMessage arrives", async () => {
    const popup = makePopup(false) as unknown as Window;
    vi.spyOn(window, "open").mockReturnValue(popup);
    mockStartOauth.mockResolvedValueOnce(resolvedOauth());

    const onCancel = vi.fn();
    const onSuccess = vi.fn();
    startOauthPopup(SocialProvider.GOOGLE, { onSuccess, onCancel, onError: vi.fn() });

    // Let the /start fetch resolve and set popup.location.href.
    await flushMicrotasks();

    // Simulate user closing the popup.
    (popup as { closed: boolean }).closed = true;
    vi.advanceTimersByTime(600); // one poll tick

    expect(onCancel).toHaveBeenCalledOnce();
    expect(onSuccess).not.toHaveBeenCalled();
  });

  it("does NOT call onCancel if success postMessage arrived first", async () => {
    const popup = makePopup(false) as unknown as Window;
    vi.spyOn(window, "open").mockReturnValue(popup);
    mockStartOauth.mockResolvedValueOnce(resolvedOauth());

    const onCancel = vi.fn();
    const onSuccess = vi.fn();
    startOauthPopup(SocialProvider.GOOGLE, { onSuccess, onCancel, onError: vi.fn() });

    await flushMicrotasks();

    // Fire a success message before closing the popup.
    window.dispatchEvent(
      new MessageEvent("message", {
        origin: window.location.origin,
        data: { type: "oauth_result", success: true },
      }),
    );

    (popup as { closed: boolean }).closed = true;
    vi.advanceTimersByTime(600);

    expect(onSuccess).toHaveBeenCalledOnce();
    expect(onCancel).not.toHaveBeenCalled();
  });
});

// ── timeout ───────────────────────────────────────────────────────────────────
describe("timeout", () => {
  it("calls onError with code=timeout after timeoutMs with no message", async () => {
    const popup = makePopup(false) as unknown as Window;
    vi.spyOn(window, "open").mockReturnValue(popup);
    mockStartOauth.mockResolvedValueOnce(resolvedOauth());

    const onError = vi.fn();
    startOauthPopup(SocialProvider.GOOGLE, {
      onSuccess: vi.fn(),
      onError,
      timeoutMs: 2000,
    });

    await flushMicrotasks();
    vi.advanceTimersByTime(2001);

    expect(onError).toHaveBeenCalledWith({ code: "timeout" });
  });
});

// ── message validation ────────────────────────────────────────────────────────
describe("postMessage validation", () => {
  it("ignores messages from a foreign origin", async () => {
    const popup = makePopup(false) as unknown as Window;
    vi.spyOn(window, "open").mockReturnValue(popup);
    mockStartOauth.mockResolvedValueOnce(resolvedOauth());

    const onSuccess = vi.fn();
    const onError = vi.fn();
    startOauthPopup(SocialProvider.GOOGLE, { onSuccess, onError });

    await flushMicrotasks();

    window.dispatchEvent(
      new MessageEvent("message", {
        origin: "https://evil.example.com",
        data: { type: "oauth_result", success: true },
      }),
    );

    expect(onSuccess).not.toHaveBeenCalled();
  });

  it("ignores messages with wrong type", async () => {
    const popup = makePopup(false) as unknown as Window;
    vi.spyOn(window, "open").mockReturnValue(popup);
    mockStartOauth.mockResolvedValueOnce(resolvedOauth());

    const onSuccess = vi.fn();
    startOauthPopup(SocialProvider.GOOGLE, { onSuccess, onError: vi.fn() });

    await flushMicrotasks();

    window.dispatchEvent(
      new MessageEvent("message", {
        origin: window.location.origin,
        data: { type: "some_other_event", success: true },
      }),
    );

    expect(onSuccess).not.toHaveBeenCalled();
  });

  it("calls onSuccess when a valid success message arrives", async () => {
    const popup = makePopup(false) as unknown as Window;
    vi.spyOn(window, "open").mockReturnValue(popup);
    mockStartOauth.mockResolvedValueOnce(resolvedOauth());

    const onSuccess = vi.fn();
    startOauthPopup(SocialProvider.GOOGLE, { onSuccess, onError: vi.fn() });

    await flushMicrotasks();

    window.dispatchEvent(
      new MessageEvent("message", {
        origin: window.location.origin,
        data: { type: "oauth_result", success: true },
      }),
    );

    expect(onSuccess).toHaveBeenCalledOnce();
  });

  it("calls onError with provider message on failure postMessage", async () => {
    const popup = makePopup(false) as unknown as Window;
    vi.spyOn(window, "open").mockReturnValue(popup);
    mockStartOauth.mockResolvedValueOnce(resolvedOauth());

    const onError = vi.fn();
    startOauthPopup(SocialProvider.GOOGLE, { onSuccess: vi.fn(), onError });

    await flushMicrotasks();

    window.dispatchEvent(
      new MessageEvent("message", {
        origin: window.location.origin,
        data: { type: "oauth_result", success: false, message: "Account exists. Please log in and link this provider explicitly." },
      }),
    );

    expect(onError).toHaveBeenCalledWith(
      expect.objectContaining({ code: "provider", message: "Account exists. Please log in and link this provider explicitly." }),
    );
  });

  it("respects the mode parameter (LINK mode passes through)", async () => {
    const popup = makePopup(false) as unknown as Window;
    vi.spyOn(window, "open").mockReturnValue(popup);
    mockStartOauth.mockResolvedValueOnce(resolvedOauth("https://accounts.google.com?link=1"));

    startOauthPopup(SocialProvider.GOOGLE, {
      mode: OAuthFlowMode.LINK,
      onSuccess: vi.fn(),
      onError: vi.fn(),
    });

    await flushMicrotasks();

    expect(mockStartOauth).toHaveBeenCalledWith(SocialProvider.GOOGLE, {
      intent: undefined,
      mode: OAuthFlowMode.LINK,
    });
  });
});
