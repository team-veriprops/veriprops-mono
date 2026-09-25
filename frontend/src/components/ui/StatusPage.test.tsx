import { describe, it, expect, afterEach } from "vitest";
import { act, type ReactElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import NotFound from "@app/not-found";
import ForbiddenPage from "@app/(website)/forbidden/page";
import ErrorPage from "@app/error";
import LoginSuccessPage from "@app/(website)/auth/login/success-redirect/page";
import { useAuthStore } from "@components/website/auth/libs/useAuthStore";
import { AuthSession, AuthUser, UserPersona, UserType } from "@components/website/auth/models";
import { ROUTES } from "@lib/routes";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const hrefs = (html: string) => [...html.matchAll(/href="([^"]*)"/g)].map((m) => m[1]);

function signIn(user: Partial<AuthUser>) {
  useAuthStore.setState({
    hydrated: true,
    session: { user: { userType: UserType.USER, personas: [], ...user } } as unknown as AuthSession,
  });
}

const mounted: Array<{ root: Root; host: HTMLElement }> = [];

/** Client-render into the document and return the resulting markup. */
function mount(ui: ReactElement): string {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  act(() => root.render(ui));
  mounted.push({ root, host });
  return host.innerHTML;
}

afterEach(() => {
  for (const { root, host } of mounted.splice(0)) {
    act(() => root.unmount());
    host.remove();
  }
  useAuthStore.setState({ hydrated: false, session: null });
});

describe("404 page", () => {
  it("offers a visible way home on the design system's primary button", () => {
    const html = renderToStaticMarkup(<NotFound />);
    const home = html.match(/<a[^>]*href="\/"[^>]*>Go back home<\/a>/)?.[0];
    expect(home).toBeDefined();
    expect(home).toContain("bg-primary");
    expect(home).toContain("text-primary-foreground");
  });
});

describe("403 page", () => {
  it("is Veriprops-branded", () => {
    const html = renderToStaticMarkup(<ForbiddenPage />);
    expect(html).toContain("Veriprops");
    expect(html).not.toMatch(/NovaStack|workspace/i);
  });

  it("offers only the way home before the session is known", () => {
    useAuthStore.setState({ hydrated: false, session: null });
    const links = hrefs(renderToStaticMarkup(<ForbiddenPage />));
    expect(links).toContain(ROUTES.HOME);
    expect(links).not.toContain(ROUTES.ADMIN.DASHBOARD);
    expect(links).not.toContain(ROUTES.PORTAL.DASHBOARD);
  });

  it("offers no dashboard to a signed-out visitor", () => {
    useAuthStore.setState({ hydrated: true, session: null });
    expect(renderToStaticMarkup(<ForbiddenPage />)).not.toContain("Go to your dashboard");
  });

  // The server render always sees the store's initial (signed-out) state, so the signed-in
  // cases are mounted as the browser would after rehydration.
  it("sends a signed-in user to their own dashboard, never a hardcoded admin one", () => {
    signIn({ personas: [UserPersona.CUSTOMER] });
    const customer = hrefs(mount(<ForbiddenPage />));
    expect(customer).toContain(ROUTES.PORTAL.DASHBOARD);
    expect(customer).not.toContain(ROUTES.ADMIN.DASHBOARD);

    signIn({ personas: [UserPersona.AGENT] });
    expect(hrefs(mount(<ForbiddenPage />))).toContain(ROUTES.AGENT.DASHBOARD);

    signIn({ userType: UserType.ADMIN });
    expect(hrefs(mount(<ForbiddenPage />))).toContain(ROUTES.ADMIN.DASHBOARD);
  });
});

describe("crash page", () => {
  it("offers a retry on the shared shell, with the brand and a route to support", () => {
    const html = renderToStaticMarkup(<ErrorPage error={new Error("boom")} reset={() => {}} />);
    expect(html).toContain("Something went wrong");
    expect(html).toMatch(/<button[^>]*bg-primary[^>]*>Try again<\/button>/);
    expect(html).toContain("Veriprops home");
    expect(html).toContain("mailto:");
  });
});

describe("login success hop", () => {
  // proxy.ts redirects every visitor off this route to the dashboard their session earns, so the
  // page can only ever guess at a destination — it must not offer one.
  it("shows progress and offers no destination", () => {
    const html = renderToStaticMarkup(<LoginSuccessPage />);
    expect(html).toContain("Signing you in");
    expect(hrefs(html)).toEqual([]);
  });
});
