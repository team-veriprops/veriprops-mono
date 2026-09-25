// @vitest-environment node
import { describe, expect, it } from "vitest";
import { NextRequest } from "next/server";
import { proxy } from "./proxy";
import { ROUTES, SIGNED_OUT_LOGIN_URL, buildAuthUrl } from "./lib/routes";
import { UserPersona, UserType } from "./components/website/auth/models";

const ORIGIN = "https://veriprops.test";

/** An unsigned token: the proxy decodes claims and expiry only, never the signature. */
function refreshToken(personas: UserPersona[] = [UserPersona.CUSTOMER]): string {
  const encode = (value: object) => Buffer.from(JSON.stringify(value)).toString("base64url");
  const exp = Math.floor(Date.now() / 1000) + 3600;
  return `${encode({ alg: "none", typ: "JWT" })}.${encode({ exp, user_type: UserType.USER, personas })}.sig`;
}

function request(path: string, { signedIn }: { signedIn: boolean }): NextRequest {
  const headers = signedIn ? { cookie: `__Host-refresh_token=${refreshToken()}` } : undefined;
  return new NextRequest(new URL(path, ORIGIN), { headers });
}

const redirectedTo = (response: Response) => {
  const location = response.headers.get("location");
  return location ? new URL(location).pathname : null;
};

describe("proxy — guest-only pages", () => {
  it("sends a live session away from the login page, to its dashboard", () => {
    expect(redirectedTo(proxy(request(ROUTES.AUTH.LOGIN, { signedIn: true })))).toBe(ROUTES.PORTAL.DASHBOARD);
  });

  it("lets the signed-out handoff through even while a session cookie survives", () => {
    // Sign-out can leave before its logout call answered (the failsafe), so the cookie may still be
    // here. Bouncing to the dashboard would put the person straight back into the app they left.
    expect(redirectedTo(proxy(request(SIGNED_OUT_LOGIN_URL, { signedIn: true })))).toBeNull();
  });

  it("does not extend the handoff to other guest-only pages", () => {
    const signup = buildAuthUrl(ROUTES.AUTH.SIGNUP, { signedOut: true });
    expect(redirectedTo(proxy(request(signup, { signedIn: true })))).toBe(ROUTES.PORTAL.DASHBOARD);
  });

  it("shows the login page to a visitor with no session", () => {
    expect(redirectedTo(proxy(request(ROUTES.AUTH.LOGIN, { signedIn: false })))).toBeNull();
  });
});

describe("proxy — protected pages", () => {
  it("sends a visitor with no session to login, remembering where they were going", () => {
    const response = proxy(request(ROUTES.PORTAL.DASHBOARD, { signedIn: false }));
    const location = new URL(response.headers.get("location")!);
    expect(location.pathname).toBe(ROUTES.AUTH.LOGIN);
    expect(location.searchParams.get("redirect")).toBe(ROUTES.PORTAL.DASHBOARD);
  });

  it("keeps a customer out of the admin console", () => {
    expect(redirectedTo(proxy(request(ROUTES.ADMIN.DASHBOARD, { signedIn: true })))).toBe(ROUTES.PORTAL.DASHBOARD);
  });
});
