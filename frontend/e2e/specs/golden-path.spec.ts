/**
 * UAT-GP — the golden-path lifecycle backbone (docs/uat-strategy.md §4).
 *
 * One ordered cross-persona journey driven entirely through the browser — the spine every
 * other area hangs off, and the producer of shared state (a real paid verification) that
 * branch specs consume.
 *
 * Currently implemented: **legs 1-5** — the customer submits and pays; an admin assigns each
 * role from the control panel; the agents accept, work, capture evidence and submit; the admin
 * returns one task for rework, then approves the lot and releases; and the customer is told,
 * passes the disclaimer gate, and reads the report and its PDF. Leg 6 (dispute / re-check) is
 * still backlog and will extend this file so the journey stays one ordered narrative.
 */
import path from "node:path";

import { Page } from "@playwright/test";

import { ROUTES } from "@lib/routes";
import { AgentRole } from "@/types/agent";
import { VerificationTier } from "@/types/verification";

import { expect, test } from "../fixtures";
import { expectNoA11yViolations } from "../helpers/a11y";
import { goto, waitReady } from "../helpers/app";
import { loginViaUi } from "../helpers/auth";
import { TEST_OTP } from "../helpers/env";
import { PERSONAS, storageStatePath } from "../helpers/personas";
import { buildScenario, scenarioAgent, ScenarioStage } from "../helpers/scenario";
import { stubPay } from "../helpers/ui";

// The seeded customer resumes any unpaid draft, so parallel runs of this journey would share one.
test.describe("UAT-GP — golden path, leg 1: submission & payment @P0 @serial", () => {
  test.use({ storageState: storageStatePath(PERSONAS.CUSTOMER) });

  test("UAT-GP-01 · a customer submits and pays for a STANDARD verification", async ({ page }) => {
    await goto(page, ROUTES.PORTAL.VERIFICATIONS_NEW);

    // ── Step 1: Property ────────────────────────────────────────────────────
    // The draft is created lazily on first change, so typing is what starts the
    // verification — nothing exists server-side until the customer commits something.
    await expect(page.getByTestId("verify-new-property")).toBeVisible();
    await page.getByTestId("verify-new-type-land").click();
    await page.getByTestId("verify-new-address").fill("Plot 15 Admiralty Way, Lekki Phase 1");
    await page.getByTestId("verify-new-landmark").fill("Opposite the roundabout");
    await page.getByTestId("verify-new-state").fill("Lagos");
    await expectNoA11yViolations(page);
    await page.getByTestId("verify-new-continue").click();

    // ── Step 2: Tier & pricing ──────────────────────────────────────────────
    await expect(page.getByTestId("verify-new-tier")).toBeVisible();
    await page.getByTestId("verify-new-tier-standard").click();
    // The customer must see a real price before committing — the quote comes from the
    // backend, never computed client-side.
    await expect(page.getByTestId("verify-new-price-ngn")).toBeVisible();
    await page.getByTestId("verify-new-continue").click();

    // ── Step 3: Consent ─────────────────────────────────────────────────────
    await expect(page.getByTestId("verify-new-consent")).toBeVisible();
    await page.getByTestId("verify-new-consent-accept").click();
    await page.getByTestId("verify-new-continue").click();

    // ── Step 4: Payment ─────────────────────────────────────────────────────
    // Submitting routes to the pay page for the newly created verification.
    await page.waitForURL(/\/portal\/verifications\/[^/]+\/pay/, { timeout: 30_000 });
    await waitReady(page);
    await expect(page.getByTestId("verify-pay")).toBeVisible();
    await expectNoA11yViolations(page);

    // The seeded customer verified their phone long ago, so the pay-step phone gate (PRD
    // §10.5) must not stand in their way. UAT-GP-02 covers the customer who hasn't.
    await expect(page.getByTestId("verify-pay-initiate")).toBeVisible();
    await expect(page.getByTestId("verify-pay-phone-gate")).toHaveCount(0);

    await stubPay(page);

    // ── Outcome: the business-observable result ─────────────────────────────
    const confirmation = page.getByTestId("verify-confirmed");
    await expect(confirmation).toBeVisible();
    // A VID the customer can quote to support, and a completion date they can hold us to.
    await expect(confirmation).toContainText(/VP-/);
    await expect(confirmation).toContainText(/Estimated completion/i);
    await expect(page.getByTestId("verify-confirmed-track")).toBeVisible();
    await expectNoA11yViolations(page);
  });
});

test.describe("UAT-GP — golden path, leg 1: first-payment phone gate @P0", () => {
  // A fresh scenario customer, logged in through the UI — never the seeded persona.
  test.use({ storageState: { cookies: [], origins: [] } });

  test("UAT-GP-02 · a customer with an unverified phone corrects their number and verifies it before paying", async ({
    page,
  }) => {
    const scenario = await buildScenario(ScenarioStage.SUBMITTED, VerificationTier.STANDARD, {
      customerPhoneVerified: false,
    });
    await loginViaUi(page, scenario.customer.email, scenario.customer.password);
    await goto(page, ROUTES.PORTAL.VERIFICATION_PAY(scenario.verificationId));
    await waitReady(page);

    // ── The gate: the number on file is shown, and payment is not offered yet (PRD §10.5) ──
    const gate = page.getByTestId("verify-pay-phone-gate");
    await expect(gate).toBeVisible();
    await expect(page.getByTestId("verify-pay-initiate")).toHaveCount(0);
    const phoneInput = page.getByTestId("verify-pay-phone-input");
    await expect(phoneInput).not.toHaveValue("");
    await expectNoA11yViolations(page);

    // ── Correct the number, receive a code, verify it ───────────────────────
    const correctedNumber = `81${Math.floor(Math.random() * 1e8).toString().padStart(8, "0")}`;
    await phoneInput.fill(correctedNumber);
    await page.getByTestId("verify-pay-send-otp").click();
    await expect(page.getByTestId("verify-pay-otp")).toBeVisible();
    // The number is locked while its code is pending; "Change number" unlocks it.
    await expect(phoneInput).toBeDisabled();
    await expect(page.getByTestId("verify-pay-change-phone")).toBeVisible();
    await expectNoA11yViolations(page);
    await page.getByTestId("verify-pay-otp").fill(TEST_OTP);
    await page.getByTestId("verify-pay-verify-otp").click();

    // ── Outcome: the gate lifts and the customer pays ───────────────────────
    await expect(gate).toBeHidden();
    await stubPay(page);
    await expect(page.getByTestId("verify-confirmed")).toContainText(scenario.vid);
    await expectNoA11yViolations(page);
  });
});

/** The roles a STANDARD verification requires, in the order the tier declares them (§1.4). */
const STANDARD_ROLES = [AgentRole.REGISTRY, AgentRole.FIELD, AgentRole.SURVEYOR] as const;

/**
 * A piece of proof-of-work every task needs before it can be submitted (§12.3). Resolved
 * against the suite's working directory, as the suite's other file paths are (helpers/env.ts).
 */
const EVIDENCE_PHOTO = path.join("e2e", "fixtures", "evidence-photo.jpg");

/**
 * Minimal valid findings per role — the required fields the backend validator enforces
 * (§12.2), typed into the same form a field agent uses.
 */
const FINDINGS: Record<AgentRole, Record<string, string>> = {
  [AgentRole.REGISTRY]: {
    registered_owner: "Chief A. Danladi",
    title_search_result: "CLEAN",
    search_reference: "LAG/REG/2026/0042",
  },
  [AgentRole.FIELD]: {
    occupancy_status: "VACANT",
    physical_condition: "Fenced, cleared plot with a block perimeter.",
  },
  [AgentRole.SURVEYOR]: {
    area_sqm: "648",
    beacon_status: "ALL_PRESENT",
  },
  [AgentRole.LAWYER]: {
    legal_opinion: "The title chain is coherent and unencumbered.",
    risk_level: "LOW",
    recommendation: "PROCEED",
  },
};

const REWORK_REASON = "The frontage photo is too dark to read the house number — please retake it.";
const REVIEW_QUALITY = "95";

/** Type this role's findings into the submission form. */
async function fillFindings(page: Page, role: AgentRole): Promise<void> {
  for (const [field, value] of Object.entries(FINDINGS[role])) {
    await page.getByTestId(`field-${field}`).fill(value);
  }
}

test.describe("UAT-GP — golden path, legs 2-5: assignment, execution, review & report @P0 @serial", () => {
  /*
   * A long journey by construction, not a slow one by accident: three agents each signing in
   * through the real form, an evidence upload apiece, a rework round-trip, a release, and four
   * accessibility scans. WebKit runs it several times slower than Chromium on a developer box,
   * so the budget is stated outright rather than left at `test.slow()`'s 270s.
   */
  test.setTimeout(600_000);

  test("UAT-GP-03 · a paid verification is assigned, worked, reviewed and released to the customer", async ({
    scenario,
    adminPage,
    pageFor,
  }) => {
    // A paid STANDARD case: its tasks exist and are waiting for an owner (§6.3).
    const journey = await scenario(ScenarioStage.PAID);

    // ── Leg 2: the admin gives each role an owner (§11.2) ───────────────────
    await goto(adminPage, ROUTES.ADMIN.VERIFICATION_DETAIL(journey.verificationId));
    await expect(adminPage.getByTestId("admin-verification-detail")).toBeVisible();
    await expectNoA11yViolations(adminPage);

    for (const role of STANDARD_ROLES) {
      const agent = scenarioAgent(journey, role);
      const taskRow = adminPage.getByTestId(`task-${role}`);
      await expect(taskRow).toContainText("Unassigned");

      // The ranked-suggestions panel is the admin's aid for choosing; it must answer, whether
      // or not this scenario's fresh agents rank into the covered area.
      await adminPage.getByTestId(`suggest-agents-${role}`).click();
      await expect(adminPage.getByTestId(`suggested-agents-${role}`)).toBeVisible();

      await adminPage.getByTestId(`assign-agent-${role}`).fill(agent.id);
      await adminPage.getByTestId(`assign-submit-${role}`).click();

      await expect(taskRow).toContainText("Assigned");
      await expect(taskRow).not.toContainText("Unassigned");
    }

    // ── Leg 3: each agent accepts the work and submits their findings (§12) ─
    const agentPages = new Map<AgentRole, Page>();
    for (const role of STANDARD_ROLES) {
      const page = await pageFor(scenarioAgent(journey, role));
      agentPages.set(role, page);

      await goto(page, ROUTES.AGENT.TASKS);
      // A scenario agent owns exactly one task: the one just assigned to them.
      await page.getByTestId(/^open-task-/).click();
      await expect(page.getByTestId("agent-task-detail")).toBeVisible();
      await expectNoA11yViolations(page);

      await page.getByTestId("detail-accept").click();
      await page.getByTestId("detail-start").click();

      // Proof-of-work first: a task cannot be submitted without it. The capture waits on the
      // browser's GPS hint (§12.3), posts a multipart body and re-reads the list, so it gets its
      // own budget rather than the 15s default that suits an ordinary re-render.
      await page.getByTestId("evidence-file").setInputFiles(EVIDENCE_PHOTO);
      await expect(page.getByTestId("agent-task-detail")).toContainText("Evidence (1)", {
        timeout: 60_000,
      });

      await fillFindings(page, role);
      await page.getByTestId("detail-submit").click();
      await expect(page.getByTestId("agent-task-detail")).toContainText("awaiting admin review");
    }

    // ── Leg 4: the admin sends one task back, and the agent reworks it (§8.1) ─
    await goto(adminPage, ROUTES.ADMIN.REPORT_REVIEW(journey.verificationId));
    await expect(adminPage.getByTestId("admin-report-review")).toBeVisible();
    await expectNoA11yViolations(adminPage);

    await adminPage.getByTestId(`reject-reason-${AgentRole.FIELD}`).fill(REWORK_REASON);
    await adminPage.getByTestId(`reject-${AgentRole.FIELD}`).click();
    await expect(adminPage.getByTestId(`review-task-${AgentRole.FIELD}`)).toContainText("Rejected");

    // The agent is told why, in their own words, and can pick the work back up.
    const fieldPage = agentPages.get(AgentRole.FIELD)!;
    await fieldPage.reload({ waitUntil: "domcontentloaded" });
    await waitReady(fieldPage);
    await expect(fieldPage.getByTestId("detail-rejection-reason")).toContainText(REWORK_REASON);

    await fieldPage.getByTestId("detail-start").click();
    // The evidence captured in the first round stands; the findings are entered afresh.
    await fillFindings(fieldPage, AgentRole.FIELD);
    await fieldPage.getByTestId("detail-submit").click();
    await expect(fieldPage.getByTestId("agent-task-detail")).toContainText("awaiting admin review");

    // ── Leg 5: the admin approves every task and releases the report (§8.3) ──
    await adminPage.reload({ waitUntil: "domcontentloaded" });
    await waitReady(adminPage);

    for (const role of STANDARD_ROLES) {
      await adminPage.getByTestId(`quality-${role}`).fill(REVIEW_QUALITY);
      await adminPage.getByTestId(`approve-${role}`).click();
      await expect(adminPage.getByTestId(`review-task-${role}`)).toContainText("Approved");
    }

    await adminPage.getByTestId("release-reason").fill("All three checks agree.");
    await adminPage.getByTestId("release-submit").click();
    // Release is the heaviest single action in the journey — composite score, commissions, the
    // versioned report and the event fan-out — so it gets its own budget rather than the 15s
    // default that suits an ordinary re-render.
    await expect(adminPage.getByTestId("admin-report-review")).toContainText("Released report v1", {
      timeout: 60_000,
    });

    // ── Leg 5: the customer is told, and reads what they paid for (§10.1) ────
    const customerPage = await pageFor(journey.customer);
    await goto(customerPage, ROUTES.PORTAL.DASHBOARD);

    // The shell keeps a bell per breakpoint in the DOM, and the off-canvas drawer's copy still
    // reads as "visible" while parked off-screen (the same trap `signOut` documents). Scoping to
    // the page header picks out the one bell the customer is actually looking at, on any viewport.
    const header = customerPage.getByRole("banner");
    const onScreen = (testId: string) => header.getByTestId(testId).filter({ visible: true });
    await expect(onScreen("notification-unread-badge")).toBeVisible();
    await onScreen("notification-bell").click();
    await expect(onScreen("notification-dropdown")).toContainText("Report ready");

    await goto(customerPage, ROUTES.PORTAL.VERIFICATION_REPORT(journey.verificationId));
    await expect(customerPage.getByTestId("verify-report")).toBeVisible();

    // The disclaimer stands between the customer and the report, once (§10.1).
    const gate = customerPage.getByTestId("report-gate-accept");
    await expect(gate).toBeVisible();
    await expectNoA11yViolations(customerPage);
    await gate.click();
    await expect(gate).toHaveCount(0);

    // The headline deliverable: a score, its band, and the VID this all belongs to.
    const gauge = customerPage.getByTestId("report-trust-score");
    await expect(gauge).toBeVisible();
    await expect(gauge).toHaveAttribute("aria-label", /Trust score \d+ out of 100/);
    await expect(customerPage.getByTestId("verify-report")).toContainText(journey.vid);
    await expectNoA11yViolations(customerPage);

    // The branded PDF is a real document the customer can keep (§10.1), fetched with their
    // own session because the link opens in a new tab rather than downloading in place.
    const pdfHref = await customerPage.getByTestId("report-download-pdf").getAttribute("href");
    const pdfResponse = await customerPage.request.get(pdfHref!);
    expect(pdfResponse.status()).toBe(200);
    const pdfBytes = await pdfResponse.body();
    expect(pdfBytes.subarray(0, 5).toString("latin1")).toBe("%PDF-");
    expect(pdfBytes.toString("latin1")).toContain(journey.vid);
  });
});
