// ─────────────────────────────────────────────────────────────────────────────
// core/runner.ts
// Executes a single domain: bootstrap → journeys → teardown.
// Respects idempotent step caching, emits events, and computes run status.
// ─────────────────────────────────────────────────────────────────────────────

import type {
  BootstrapStep,
  Domain,
  DomainRunResult,
  DomainRunStatus,
  Journey,
  JourneyResult,
  QAConfig,
  SessionFixture,
} from "./types.js";
import { eventBus } from "./event-bus.js";
import { BrowserRunner } from "./browser-runner.js";
import { FlowEngine } from "./flow-engine.js";
import { APIRunner } from "./api-runner.js";
import { BackendAdapter } from "../adapters/backend.js";
import {
  buildCacheKey,
  isCached,
  setCached,
} from "./cache.js";

export class DomainRunner {
  private config: QAConfig;
  private runId: string;

  constructor(config: QAConfig, runId: string) {
    this.config = config;
    this.runId = runId;
  }

  // ─── Domain execution ─────────────────────────────────────────────────────

  async runDomain(domain: Domain): Promise<DomainRunResult> {
    const domainName = domain.contract.name;
    const startedAt = Date.now();

    await eventBus.emit("domain:start", { runId: this.runId, domainName });

    let journeyResults: JourneyResult[] = [];

    try {
      // Bootstrap all declared sessions
      for (const session of domain.fixtures.sessions) {
        await this.runBootstrap(session, domainName);
      }

      // Run all journeys
      journeyResults = await this.runJourneys(domain);

      // Teardown all declared sessions
      for (const session of domain.fixtures.sessions) {
        if (session.teardown && session.teardown.length > 0) {
          await this.runTeardown(session, domainName);
        }
      }
    } catch (err) {
      const error = err instanceof Error ? err.message : String(err);
      const durationMs = Date.now() - startedAt;

      const result: DomainRunResult = {
        domainName,
        status: "error",
        journeys: journeyResults,
        durationMs,
        error,
      };

      await eventBus.emit("domain:end", { runId: this.runId, domainName, result });
      return result;
    }

    const durationMs = Date.now() - startedAt;
    const status = this.computeStatus(journeyResults);

    const result: DomainRunResult = {
      domainName,
      status,
      journeys: journeyResults,
      durationMs,
    };

    await eventBus.emit("domain:end", { runId: this.runId, domainName, result });
    return result;
  }

  // ─── Bootstrap ────────────────────────────────────────────────────────────

  async runBootstrap(session: SessionFixture, domainName: string): Promise<void> {
    const backend = new BackendAdapter(this.config);

    for (const step of session.bootstrap) {
      await this.executeBootstrapStep(step, domainName, backend);
    }
  }

  async runTeardown(session: SessionFixture, domainName: string): Promise<void> {
    if (!session.teardown) return;
    const backend = new BackendAdapter(this.config);

    for (const step of session.teardown) {
      // Teardown steps are never cached
      await this.executeBootstrapStep(
        { ...step, idempotent: false },
        domainName,
        backend
      );
    }
  }

  private async executeBootstrapStep(
    step: BootstrapStep,
    domainName: string,
    backend: BackendAdapter
  ): Promise<void> {
    // Check idempotent cache
    if (step.idempotent) {
      const key = buildCacheKey(domainName, step.label, step.action, step.payload);
      if (isCached(key, this.config.cacheTtl)) {
        await eventBus.emit("cache:hit", { stepLabel: step.label, domainName });
        console.log(`[runner] Cache hit — skipping idempotent step: "${step.label}"`);
        return;
      }
      await eventBus.emit("cache:miss", { stepLabel: step.label, domainName });
    }

    console.log(`[runner] Bootstrap step: "${step.label}" (${step.action})`);
    await backend.bootstrap(step.action, step.payload);

    // Store in cache after successful execution
    if (step.idempotent) {
      const key = buildCacheKey(domainName, step.label, step.action, step.payload);
      const hash = JSON.stringify(step.payload ?? {});
      setCached(key, hash);
    }
  }

  // ─── Journey dispatch ─────────────────────────────────────────────────────

  private async runJourneys(domain: Domain): Promise<JourneyResult[]> {
    const results: JourneyResult[] = [];

    const browserJourneys = domain.journeys.filter((j) => j.mode === "browser");
    const apiJourneys = domain.journeys.filter((j) => j.mode === "api");

    // API journeys — no browser needed
    if (apiJourneys.length > 0) {
      const apiResults = await this.runApiJourneys(domain, apiJourneys);
      results.push(...apiResults);
    }

    // Browser journeys — share one browser instance per domain
    if (browserJourneys.length > 0) {
      const browserResults = await this.runBrowserJourneys(domain, browserJourneys);
      results.push(...browserResults);
    }

    return results;
  }

  private async runApiJourneys(
    domain: Domain,
    journeys: Journey[]
  ): Promise<JourneyResult[]> {
    const apiRunner = new APIRunner(this.config);
    const engine = new FlowEngine(this.config, this.runId, domain.contract.name);
    const results: JourneyResult[] = [];

    for (const journey of journeys) {
      const result = await engine.executeJourney(
        journey,
        domain.selectors,
        undefined,
        apiRunner
      );
      results.push(result);
    }

    return results;
  }

  private async runBrowserJourneys(
    domain: Domain,
    journeys: Journey[]
  ): Promise<JourneyResult[]> {
    const browserRunner = new BrowserRunner(this.config, this.runId);
    const results: JourneyResult[] = [];

    await browserRunner.launch();

    try {
      for (const journey of journeys) {
        const result = await browserRunner.runJourney(journey, domain);
        results.push(result);
      }
    } finally {
      await browserRunner.close();
    }

    return results;
  }

  // ─── Status computation ───────────────────────────────────────────────────

  computeStatus(journeyResults: JourneyResult[]): DomainRunStatus {
    if (journeyResults.length === 0) return "skipped";

    const statuses = journeyResults.map((j) => j.status);
    const allPass = statuses.every((s) => s === "pass");
    const allSkip = statuses.every((s) => s === "skip");
    const anyFail = statuses.some((s) => s === "fail" || s === "error");
    const anyPass = statuses.some((s) => s === "pass");

    if (allPass) return "pass";
    if (allSkip) return "skipped";
    if (anyFail && anyPass) return "partial";
    if (anyFail) return "fail";
    return "partial";
  }
}
