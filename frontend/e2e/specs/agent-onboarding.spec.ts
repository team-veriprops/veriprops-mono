/**
 * UAT-AGENT — becoming a verified agent (PRD §3.1, docs/uat-strategy.md §6.3).
 *
 * Applying is a compulsory gate, not a page: an account with no application, or a rejected one,
 * meets the non-dismissible wizard on every `/agents/*` route except the application itself.
 * Getting there is part of the journey — `proxy.ts` lets only the AGENT persona near those routes,
 * and that persona is granted by signing up with `?intent=agent`, so each applicant here is a real
 * new account that came in through the agent path.
 *
 * The last two scenarios are the same journey in opposite directions (§3.2, personas are
 * additive): a customer takes up the agent hat, an agent takes up the customer hat. Both must work
 * **in the session the person is already in** — the grant reaches the database immediately, but
 * the route guard reads the refresh token, so the newly granted area stays shut unless the backend
 * rotates the session. Landing on the other side without signing in again is that proof.
 *
 * Identity is deterministic: the KYC stub fails `00000000000` and passes anything else
 * (`appodus_utils/integrations/kyc/stub/stub_kyc.py`), so the unhappy path needs no fixture.
 */
import { Page } from "@playwright/test";

import { ROUTES } from "@lib/routes";
import { DATATABLE_TEST_IDS } from "@components/ui/table/testIds";
import { UserPersona } from "@components/website/auth/models";

import { expect, test } from "../fixtures";
import { expectNoA11yViolations } from "../helpers/a11y";
import { goto, waitForHydration, waitForPage, waitReady } from "../helpers/app";
import { ScenarioStage } from "../helpers/scenario";
import { NewAccount, signUpViaUi } from "../helpers/signup";
import { openNavItem } from "../helpers/ui";

/** The KYC stub's failing identity; every other number passes. */
const FAILING_BVN = "00000000000";
const PASSING_BVN = "22222222222";
const SURVEYOR_LICENCE = "SURCON/2026/4471";

/** Sign a new applicant up through the agent path and follow them to the compulsory gate. */
async function arriveAtTheGate(page: Page): Promise<NewAccount> {
  const account = await signUpViaUi(page, { intent: "agent" });

  await waitForPage(page, (url) => url.pathname.startsWith(ROUTES.AGENT.GATE), { timeout: 30_000 });
  await expect(page.getByTestId("agent-apply-overlay")).toBeVisible();

  return account;
}

/**
 * Walk the wizard end to end from the gate. FIELD needs no licence and SURVEYOR does, so this
 * covers both the plain and the credential-gated path in one application.
 */
async function applyAsAgent(page: Page, bvn: string): Promise<void> {
  await page.getByTestId("agent-apply-role-field").click();
  await page.getByTestId("agent-apply-role-surveyor").click();
  await page.getByTestId("agent-apply-continue").click();

  // BVN is the wizard's default method, so its field is already the one on screen.
  await expect(page.getByTestId("agent-apply-kyc")).toBeVisible();
  await page.getByTestId("agent-apply-bvn").fill(bvn);
  await page.getByTestId("agent-apply-continue").click();

  // The wizard will not advance until every licence-bearing role has its number.
  await expect(page.getByTestId("agent-apply-credentials")).toBeVisible();
  await page.getByTestId("agent-apply-licence-surveyor").fill(SURVEYOR_LICENCE);
  await page.getByTestId("agent-apply-continue").click();

  await expect(page.getByTestId("agent-apply-review")).toBeVisible();
  await page.getByTestId("agent-apply-truthfulness").click();
  await page.getByTestId("agent-apply-terms").click();
  await page.getByTestId("agent-apply-submit").click();

  await expect(page.getByTestId("agent-status-card")).toBeVisible();
}

/**
 * Prove the account now wears both hats and can move between them.
 *
 * `PortalSwitcher` renders only for two or more personas, so its presence *is* the assertion that
 * the grant reached this browser — and the crossing itself is what a user would do next. Which hat
 * to cross *to* is read off the current URL, exactly as the switcher reads it: passing it in got
 * the direction wrong in both scenarios, because the hat someone just took up is not the portal
 * they are standing in.
 */
async function expectBothHats(page: Page): Promise<void> {
  const inAgentArea = new URL(page.url()).pathname.startsWith(ROUTES.AGENT.GATE);
  const to = inAgentArea ? UserPersona.CUSTOMER : UserPersona.AGENT;
  const destination = inAgentArea ? ROUTES.PORTAL.DASHBOARD : ROUTES.AGENT.DASHBOARD;

  const switcher = page.getByTestId("portal-switch").filter({ visible: true }).first();
  await expect(switcher).toBeVisible();

  // The dropdown's items mount on open, and a click landing before it is interactive only focuses
  // the trigger — the same retry shape `signOut` uses on the user menu.
  const crossing = page.getByTestId(`portal-switch-to-${to}`);
  await expect(async () => {
    if ((await switcher.getAttribute("aria-expanded")) !== "true") await switcher.click();
    await expect(crossing).toBeVisible({ timeout: 2_000 });
  }).toPass({ timeout: 15_000 });
  await crossing.click();

  await waitForPage(page, (url) => url.pathname.startsWith(destination), { timeout: 30_000 });
}

/** Find one applicant's application in the admin queue and open it. */
async function openApplication(adminPage: Page, email: string): Promise<void> {
  await adminPage.goto(ROUTES.ADMIN.AGENT_APPLICATIONS, { waitUntil: "domcontentloaded" });
  await waitReady(adminPage);
  await expect(adminPage.getByTestId("admin-agent-applications")).toBeVisible();

  // Scoped by the applicant's own address, so a parallel spec's application cannot be mistaken
  // for this one. The search is a controlled input, so it has to be hydrated before it is typed
  // into: text that lands first is discarded when React takes over, and a half-written address
  // matches nobody — which reads as "the application is missing" rather than as a lost keystroke.
  await waitForHydration(adminPage, DATATABLE_TEST_IDS.SEARCH);
  await adminPage.getByTestId(DATATABLE_TEST_IDS.SEARCH).fill(email);
  const row = adminPage.getByTestId(DATATABLE_TEST_IDS.ROW);
  await expect(row).toHaveCount(1);
  // The queue itself, while nothing covers it — its filter, pager and scroll region are the
  // shared DataTable every admin list renders.
  await expectNoA11yViolations(adminPage);
  await row.click();

  await expect(adminPage.getByTestId("admin-agent-detail")).toBeVisible();
}

/**
 * Record the admin's decision and wait until the server has accepted it. The drawer closes only
 * once the decision is saved, so that is the point after which the applicant's page can be
 * reloaded to see the outcome — reloading straight after the click can read the application
 * before the decision lands, and the page then shows "Pending review" with nothing to refresh it.
 */
async function decideApplication(adminPage: Page, decisionTestId: string): Promise<void> {
  await adminPage.getByTestId(decisionTestId).click();
  await expect(adminPage.getByTestId("admin-agent-detail")).toBeHidden();
}

test.describe("UAT-AGENT — agent onboarding @P1", () => {
  // Signing up is a signed-out journey, so these must not inherit a session.
  test.use({ storageState: { cookies: [], origins: [] } });
  // A full signup, four wizard steps, an admin decision and a round trip back to the applicant.
  test.slow();

  test("UAT-AGENT-01 · an applicant is held at the gate until they apply, then waits for review", async ({
    page,
  }) => {
    await arriveAtTheGate(page);

    // ── The gate is compulsory, and it offers no way out (§3.1) ─────────────
    await expect(page.getByTestId("agent-apply-close")).toHaveCount(0);
    await expect(page.getByTestId("agent-apply-roles")).toBeVisible();
    await expectNoA11yViolations(page);

    // ── Roles: one that needs a licence and one that does not ───────────────
    await page.getByTestId("agent-apply-role-field").click();
    await page.getByTestId("agent-apply-role-surveyor").click();
    await page.getByTestId("agent-apply-continue").click();

    // ── Identity ────────────────────────────────────────────────────────────
    await expect(page.getByTestId("agent-apply-kyc")).toBeVisible();
    await expectNoA11yViolations(page);
    await page.getByTestId("agent-apply-bvn").fill(PASSING_BVN);
    await page.getByTestId("agent-apply-continue").click();

    // ── Credentials ─────────────────────────────────────────────────────────
    await expect(page.getByTestId("agent-apply-credentials")).toBeVisible();
    await expectNoA11yViolations(page);
    await page.getByTestId("agent-apply-licence-surveyor").fill(SURVEYOR_LICENCE);
    await page.getByTestId("agent-apply-continue").click();

    // ── Review & submit ─────────────────────────────────────────────────────
    await expect(page.getByTestId("agent-apply-review")).toBeVisible();
    await expectNoA11yViolations(page);
    await page.getByTestId("agent-apply-truthfulness").click();
    await page.getByTestId("agent-apply-terms").click();
    await page.getByTestId("agent-apply-submit").click();

    // ── Outcome: the gate lifts, and the applicant is told where they stand ─
    const statusCard = page.getByTestId("agent-status-card");
    await expect(statusCard).toBeVisible();
    await expect(statusCard).toContainText("Pending review");
    await expect(statusCard).toContainText("don't receive jobs yet");
    // Work stays shut until an admin says otherwise.
    await expect(page.getByText("Your tasks")).toHaveCount(0);
    await expectNoA11yViolations(page);
  });

  test("UAT-AGENT-02 · an admin approves the application and the agent's own area opens up", async ({
    page,
    adminPage,
  }) => {
    const account = await arriveAtTheGate(page);
    await applyAsAgent(page, PASSING_BVN);

    await openApplication(adminPage, account.email);
    // The applicant's address is the drawer's reference, rendered in its header — beside the
    // detail body rather than inside it.
    await expect(adminPage.getByTestId("detail-drawer")).toContainText(account.email);
    // Scoped to the drawer: it is `aria-modal`, so the page behind its backdrop is inert. Scanning
    // through it also raced the drawer's JS-driven slide-in, which the helper's animation wait
    // cannot see — axe then read the sidebar under a half-faded backdrop (1.03:1). The queue
    // behind it was already scanned uncovered, in `openApplication`.
    await expectNoA11yViolations(adminPage, { include: '[data-testid="detail-drawer"]' });
    await decideApplication(adminPage, "admin-agent-approve");

    await page.reload({ waitUntil: "domcontentloaded" });
    await waitReady(page);

    const statusCard = page.getByTestId("agent-status-card");
    await expect(statusCard).toContainText("Approved");
    await expect(statusCard).toContainText("Active roles");
    // The workload the approval unlocks.
    await expect(page.getByText("Your tasks")).toBeVisible();
    await expectNoA11yViolations(page);
  });

  test("UAT-AGENT-03 · a failed identity check is rejected, and the applicant is told why", async ({
    page,
    adminPage,
  }) => {
    const account = await arriveAtTheGate(page);
    await applyAsAgent(page, FAILING_BVN);

    await openApplication(adminPage, account.email);
    // The admin decides on what the identity check actually reported.
    await expect(adminPage.getByTestId("admin-agent-detail")).toContainText("Failed");

    const reason = "The BVN check did not pass, so we could not confirm your identity.";
    await adminPage.getByTestId("admin-agent-reject-reason").fill(reason);
    await decideApplication(adminPage, "admin-agent-reject");

    // ── Outcome: rejection sends the applicant back through the gate (§3.1) ──
    await page.reload({ waitUntil: "domcontentloaded" });
    await waitReady(page);
    await expect(page.getByTestId("agent-apply-overlay")).toBeVisible();

    // And it has to say why: sent back into an identical blank wizard with no reason, the
    // applicant can only resubmit the same application and be refused again.
    await expect(page.getByTestId("agent-apply-rejection-reason")).toContainText(reason);
  });

  test("UAT-AGENT-04 · an existing customer becomes an agent in the session they are already in", async ({
    scenario,
    pageFor,
  }) => {
    // A customer, not an agent-intent signup: this is the journey someone already using the
    // product takes. It needs a fresh account — handing the seeded customer an agent hat would
    // change where every other spec expects them to land.
    const { customer } = await scenario(ScenarioStage.DRAFT);
    const page = await pageFor(customer);
    await goto(page, ROUTES.PORTAL.DASHBOARD);

    // The way in from inside the portal. Someone who never revisits the marketing pages has to
    // be able to find it, and the marketing call to action is guest-only.
    await openNavItem(page, "Become an Agent");

    await waitForPage(page, (url) => url.pathname === ROUTES.AGENT.APPLY, { timeout: 30_000 });
    await expect(page.getByTestId("agent-apply-overlay")).toBeVisible();
    // A way out. The overlay covers the nav, so a customer who changes their mind here would
    // otherwise be stuck with nothing but the URL bar — §3.1's compulsory gate binds the agent
    // area, not the application someone came to look at.
    await expect(page.getByTestId("agent-apply-close")).toBeVisible();
    await expectNoA11yViolations(page);

    await applyAsAgent(page, PASSING_BVN);

    // ── The persona is live in this session, not the next one ───────────────
    // Applying grants AGENT server-side, but the route guard reads the refresh token — so unless
    // the backend rotated this session, the push to the agent area is bounced straight back.
    // Arriving on the status card at all is what proves rotation happened.
    await expect(page.getByTestId("agent-status-card")).toContainText("Pending review");

    // ── Both hats, switchable ───────────────────────────────────────────────
    await expectBothHats(page);
    await expectNoA11yViolations(page);
  });

  test("UAT-AGENT-05 · an agent takes up the customer hat and can have a property verified", async ({
    page,
  }) => {
    // The mirror of UAT-AGENT-04. Signing up through the agent path grants AGENT alone, so this
    // account has no portal at all until it asks for one.
    await arriveAtTheGate(page);
    await applyAsAgent(page, PASSING_BVN);

    // The way in from inside the agent area, for the same reason the portal needed one: the
    // marketing call to action is guest-only, so a signed-in agent is turned away from it.
    await openNavItem(page, "Verify a Property");

    // ── It ends in the wizard, with no second sign-in ───────────────────────
    // The interstitial that acknowledges the wait is not asserted here: on a fast stack the grant
    // lands before a check could see it, which is the right outcome. Its wording is pinned by
    // `VerifyPropertyContainer.test.tsx` instead.
    await waitForPage(page, (url) => url.pathname === ROUTES.PORTAL.VERIFICATIONS_NEW, { timeout: 30_000 });
    await expect(page.getByTestId("verify-new-overlay")).toBeVisible();
    await expectNoA11yViolations(page);

    // The wizard is a full-screen layer over the shell, so leave it before reaching for the
    // switcher that lives in the chrome underneath.
    await goto(page, ROUTES.PORTAL.DASHBOARD);
    await expectBothHats(page);
  });
});
