import { NextRequest, NextResponse } from "next/server";

/**
 * Centralised auth guard (Next.js 16 "Proxy" — formerly Middleware).
 *
 * Optimistic check only: does the request carry the HttpOnly access-token
 * cookie set by the backend? Rejecting unauthenticated traffic at the edge
 * avoids round-tripping protected pages through the React tree, but the
 * actual session validity is still enforced server-side by FastAPI on every
 * `/api/users/auth/*` call (and by `useCurrentSession` on the client).
 *
 * Per Next.js docs: "Proxy is *not* intended for slow data fetching … it
 * should not be used as a full session management solution." We only check
 * cookie presence here.
 */

const ACCESS_COOKIE = "access_token";
const LOGIN_PATH = "/auth/login";

// Surfaces that require an authenticated session.
const PROTECTED_PREFIXES = [
  "/portal",
  "/admin",
  "/agent",     // agent dashboard / onboarding
  "/agents",    // legacy / agents-facing surface
  "/account",
];

// Surfaces that should be hidden from already-authenticated users.
const GUEST_ONLY_PATHS = new Set<string>([
  "/auth/login",
  "/auth/signup",
  "/auth", // gate page is also guest-only
]);

const isProtected = (pathname: string) =>
  PROTECTED_PREFIXES.some((p) => pathname === p || pathname.startsWith(`${p}/`));

const isGuestOnly = (pathname: string) => GUEST_ONLY_PATHS.has(pathname);

export function proxy(req: NextRequest) {
  const { pathname, search } = req.nextUrl;
  const hasSession = req.cookies.has(ACCESS_COOKIE);

  if (isProtected(pathname) && !hasSession) {
    const target = req.nextUrl.clone();
    target.pathname = LOGIN_PATH;
    target.search = "";
    target.searchParams.set("redirect", `${pathname}${search ?? ""}`);
    return NextResponse.redirect(target);
  }

  if (isGuestOnly(pathname) && hasSession) {
    const target = req.nextUrl.clone();
    target.pathname = "/portal/dashboard";
    target.search = "";
    return NextResponse.redirect(target);
  }

  return NextResponse.next();
}

export const config = {
  // Only run on routes that actually need the guard. Skip Next internals,
  // static assets, and the public marketing site.
  matcher: [
    "/portal/:path*",
    "/admin/:path*",
    "/agent/:path*",
    "/agents/:path*",
    "/account/:path*",
    "/auth",
    "/auth/login",
    "/auth/signup",
  ],
};
