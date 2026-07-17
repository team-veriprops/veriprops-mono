import { NextRequest, NextResponse } from "next/server";
import { jwtDecode } from "jwt-decode";
import { ROUTES } from "./lib/routes";
import { EDGE_AUTH_HEADER, isEdgeAuthorized } from "./lib/edgeAuth";
import { JwtPayload, UserPersona, UserType } from "./components/website/auth/models";

/**
 * Centralised auth guard (Next.js 16 Proxy).
 *
 * Fast edge validation only:
 * - JWT cookie exists
 * - JWT is structurally valid
 * - JWT has exp claim
 * - JWT is not expired
 *
 * Signature verification is intentionally skipped at the edge.
 * Backend remains the source of truth.
 * 
 * Per Next.js docs: "Proxy is *not* intended for slow data fetching … it
 * should not be used as a full session management solution." We only check
 * cookie presence here.
 */

const ACCESS_COOKIE_KEY = "__Host-access_token";

const LOGIN_PATH = ROUTES.AUTH.LOGIN;
const HOME_PATH = ROUTES.HOME ?? "/";

const ADMIN_DASHBOARD = ROUTES.ADMIN.DASHBOARD;
const PORTAL_DASHBOARD = ROUTES.PORTAL.DASHBOARD;
const AGENT_DASHBOARD = ROUTES.AGENT.DASHBOARD;

// Surfaces that require an authenticated session.
const PROTECTED_PREFIXES = [
  ROUTES.PORTAL.GATE,
  ROUTES.ADMIN.GATE,
  ROUTES.AGENT.GATE,
  ROUTES.ACCOUNT.ROOT,
  ROUTES.AUTH.LOGIN_SUCCESS_REDIRECT
] as const;

// Surfaces hidden from authenticated users.
const GUEST_ONLY_PATHS = new Set<string>([
  ROUTES.AUTH.LOGIN,
  ROUTES.AUTH.SIGNUP,
  ROUTES.AUTH.GATE,
]);

const isProtected = (pathname: string) =>
  PROTECTED_PREFIXES.some(
    (p) => pathname === p || pathname.startsWith(`${p}/`)
  );

const isGuestOnly = (pathname: string) => GUEST_ONLY_PATHS.has(pathname);


/**
 * Expiry validation
 */
function hasValidSession(decodedJwt: JwtPayload | undefined): boolean {
  if (!decodedJwt?.exp) return false;
  return decodedJwt.exp > Math.floor(Date.now() / 1000);
}

/**
 * Normalize personas once
 */
function getPersonas(jwt?: JwtPayload): UserPersona[] {
  return jwt?.personas ?? [];
}

/**
 * Role routing
 */
function redirectToDashboard(decodedJwt?: JwtPayload): string {
  if (!decodedJwt) return LOGIN_PATH;

  if (decodedJwt.user_type === UserType.ADMIN) return ADMIN_DASHBOARD;

  const personas = getPersonas(decodedJwt);

  if (decodedJwt.user_type === UserType.USER){
    if(personas?.includes(UserPersona.AGENT)) return AGENT_DASHBOARD;
    if(personas?.includes(UserPersona.CUSTOMER)) return PORTAL_DASHBOARD;
  }

  return HOME_PATH;
}

/**
 * Decode JWT safely
 */
function decodeJwt(jwtToken?: string): JwtPayload | undefined {
  if (!jwtToken) return undefined;

  try {
    return jwtDecode<JwtPayload>(jwtToken);
  } catch {
    return undefined;
  }
}

function redirect(req: NextRequest, path: string) {
  return NextResponse.redirect(new URL(path, req.url));
}

export function proxy(req: NextRequest) {
  // 0. Trusted-edge check — reject traffic that bypassed the Cloudflare proxy
  // (e.g. direct *.vercel.app URLs). No-op while EDGE_AUTH_SECRET is unset.
  if (!isEdgeAuthorized(req.headers.get(EDGE_AUTH_HEADER), process.env.EDGE_AUTH_SECRET)) {
    return NextResponse.json(
      { error: { code: "EDGE_AUTH_REQUIRED", message: "Requests must come through the trusted edge." } },
      { status: 403 },
    );
  }

  const { pathname, search } = req.nextUrl;
  const jwtToken = req.cookies.get(ACCESS_COOKIE_KEY)?.value;

  // 1. No token → short-circuit
  if (!jwtToken) {
    if (isProtected(pathname)) {
      const target = req.nextUrl.clone();
      target.pathname = LOGIN_PATH;
      target.search = "";
      target.searchParams.set("redirect", `${pathname}${search || ""}`);
      return NextResponse.redirect(target);
    }
    return NextResponse.next();
  }

  const decodedJwt = decodeJwt(jwtToken);
  const hasSession = hasValidSession(decodedJwt);

  // 2. Invalid/expired token handling
  if (!hasSession) {
    if (isProtected(pathname)) {
      const target = req.nextUrl.clone();
      target.pathname = LOGIN_PATH;
      target.search = "";
      target.searchParams.set("redirect", `${pathname}${search || ""}`);
      return NextResponse.redirect(target);
    }
    return NextResponse.next();
  }

  const personas = getPersonas(decodedJwt);

  const isAdmin = decodedJwt?.user_type === UserType.ADMIN;
  const isAgent = personas.includes(UserPersona.AGENT);
  const isCustomer = personas.includes(UserPersona.CUSTOMER);

  const isOnLoginRedirect = pathname.startsWith(ROUTES.AUTH.LOGIN_SUCCESS_REDIRECT);
  const isOnAgent = pathname.startsWith(ROUTES.AGENT.GATE);
  const isOnAdmin = pathname.startsWith(ROUTES.ADMIN.GATE);
  const isOnPortal = pathname.startsWith(ROUTES.PORTAL.GATE);

  // 3. Guest-only routes
  if (isGuestOnly(pathname)) {
    return redirect(req, redirectToDashboard(decodedJwt));
  }

  // 4. Role enforcement
  if (isOnAdmin && !isAdmin) {
    return redirect(req, redirectToDashboard(decodedJwt));
  }

  if (isOnAgent && !isAdmin && !isAgent) {
    return redirect(req, redirectToDashboard(decodedJwt));
  }

  if (isOnPortal && !isAdmin && !isCustomer) {
    return redirect(req, redirectToDashboard(decodedJwt));
  }

  // 5. Post-login cleanup
  if (isOnLoginRedirect) {
    return redirect(req, redirectToDashboard(decodedJwt));
  }

  return NextResponse.next();
}

export const config = {

  // The trusted-edge check must see EVERY request, so match all routes except
  // Next internals/static assets. The auth guard stays scoped by its own
  // pathname checks (isProtected/isGuestOnly), so the wider matcher does not
  // change guard behavior on public marketing pages.
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
