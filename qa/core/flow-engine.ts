// ─────────────────────────────────────────────────────────────────────────────
// core/flow-engine.ts
// Executes journeys step by step.
// Dispatches each step type, resolves selectors and interpolated values,
// captures forensic artifacts on failure, and emits structured events.
// ─────────────────────────────────────────────────────────────────────────────

import type { Page } from "@playwright/test";
import type {
  Journey,
  JourneyResult,
  Step,
  StepContext,
  StepResult,
  QAConfig,
  SelectorMap,
} from "./types.js";
import { eventBus } from "./event-bus.js";
import { ForensicCapture } from "./forensic.js";
import { APIRunner } from "./api-runner.js";

// ─── FlowEngine ───────────────────────────────────────────────────────────────

export class FlowEngine {
  private config: QAConfig;
  private runId: string;
  private domainName: string;

  constructor(config: QAConfig, runId: string, domainName: string) {
    this.config = config;
    this.runId = runId;
    this.domainName = domainName;
  }

  // ─── Journey execution ────────────────────────────────────────────────────

  async executeJourney(
    journey: Journey,
    selectors: SelectorMap,
    page?: Page,
    apiRunner?: APIRunner
  ): Promise<JourneyResult> {
    const startedAt = Date.now();
    const stepResults: StepResult[] = [];

    if (journey.skip) {
      return {
        journeyName: journey.name,
        status: "skip",
        steps: [],
        durationMs: 0,
      };
    }

    await eventBus.emit("journey:start", {
      runId: this.runId,
      domainName: this.domainName,
      journeyName: journey.name,
    });

    const forensic = new ForensicCapture(
      this.runId,
      this.domainName,
      journey.name,
      this.config.artifactsDir
    );

    const ctx: StepContext = {
      config: this.config,
      state: {},
      selectors,
      sessionKey: journey.sessionKey,
    };

    let cascadeFailed = false;

    for (const step of journey.steps) {
      if (cascadeFailed && !step.optional) {
        const skipped: StepResult = {
          label: step.label,
          type: step.type,
          status: "skip",
          durationMs: 0,
        };
        stepResults.push(skipped);
        await eventBus.emit("step:skip", {
          runId: this.runId,
          domainName: this.domainName,
          label: step.label,
        });
        continue;
      }

      const result = await this.executeStep(step, ctx, forensic, page, apiRunner);
      stepResults.push(result);

      if (result.status === "fail") {
        await eventBus.emit("step:fail", {
          runId: this.runId,
          domainName: this.domainName,
          label: step.label,
          error: result.error ?? "unknown",
        });

        if (!step.optional) cascadeFailed = true;
      } else if (result.status === "pass") {
        await eventBus.emit("step:pass", {
          runId: this.runId,
          domainName: this.domainName,
          label: step.label,
          durationMs: result.durationMs,
        });
      }
    }

    const durationMs = Date.now() - startedAt;
    const failed = stepResults.filter((s) => s.status === "fail");
    const allSkipped = stepResults.every((s) => s.status === "skip");

    const status = failed.length > 0 ? "fail" : allSkipped ? "skip" : "pass";

    const journeyResult: JourneyResult = {
      journeyName: journey.name,
      status,
      steps: stepResults,
      durationMs,
    };

    await eventBus.emit("journey:end", {
      runId: this.runId,
      domainName: this.domainName,
      result: journeyResult,
    });

    forensic.writeReport(journeyResult);
    return journeyResult;
  }

  // ─── Step execution ───────────────────────────────────────────────────────

  private async executeStep(
    step: Step,
    ctx: StepContext,
    forensic: ForensicCapture,
    page?: Page,
    apiRunner?: APIRunner
  ): Promise<StepResult> {
    const start = Date.now();

    try {
      await this.dispatch(step, ctx, page, apiRunner);

      return {
        label: step.label,
        type: step.type,
        status: "pass",
        durationMs: Date.now() - start,
      };
    } catch (err) {
      const error = err instanceof Error ? err.message : String(err);

      // Capture forensic artifacts on failure
      if (page) {
        await forensic.captureScreenshot(page, step.label).catch(() => {});
        await forensic.captureDOMSnapshot(page, step.label).catch(() => {});
      }
      forensic.writeLog([`FAIL [${step.type}] ${step.label}: ${error}`]);

      return {
        label: step.label,
        type: step.type,
        status: "fail",
        durationMs: Date.now() - start,
        error,
      };
    }
  }

  // ─── Step dispatcher ──────────────────────────────────────────────────────

  private async dispatch(
    step: Step,
    ctx: StepContext,
    page?: Page,
    apiRunner?: APIRunner
  ): Promise<void> {
    switch (step.type) {
      case "navigate": {
        this.requirePage(page, step.type);
        const url = this.resolveValue(step.url ?? "", ctx, step.label, "url");
        await page!.goto(url, { timeout: this.config.timeout });
        break;
      }

      case "click": {
        this.requirePage(page, step.type);
        const selector = this.resolveSelector(step.selector ?? "", ctx, step.label);
        await page!.click(selector, { timeout: this.config.timeout });
        break;
      }

      case "fill": {
        this.requirePage(page, step.type);
        const selector = this.resolveSelector(step.selector ?? "", ctx, step.label);
        const value = this.resolveValue(step.value ?? "", ctx, step.label, "value");
        await page!.fill(selector, value, { timeout: this.config.timeout });
        break;
      }

      case "select": {
        this.requirePage(page, step.type);
        const selector = this.resolveSelector(step.selector ?? "", ctx, step.label);
        const value = this.resolveValue(step.value ?? "", ctx, step.label, "value");
        await page!.selectOption(selector, value, { timeout: this.config.timeout });
        break;
      }

      case "wait": {
        const duration = step.duration ?? 1000;
        await new Promise((r) => setTimeout(r, duration));
        break;
      }

      case "wait-for-selector": {
        this.requirePage(page, step.type);
        const selector = this.resolveSelector(step.selector ?? "", ctx, step.label);
        await page!.waitForSelector(selector, { timeout: this.config.timeout });
        break;
      }

      case "wait-for-network": {
        this.requirePage(page, step.type);
        await page!.waitForLoadState("networkidle", { timeout: this.config.timeout });
        break;
      }

      case "assert": {
        if (!step.assertion) throw new Error(`Step "${step.label}" has type "assert" but no assertion function`);
        const result = await step.assertion();
        if (result.status === "fail") {
          throw new Error(
            `Assertion failed: ${result.message}` +
              (result.actual !== undefined ? ` | actual: ${JSON.stringify(result.actual)}` : "") +
              (result.expected !== undefined ? ` | expected: ${JSON.stringify(result.expected)}` : "")
          );
        }
        break;
      }

      case "screenshot": {
        this.requirePage(page, step.type);
        const label = step.label ?? "manual-screenshot";
        const filename = `${label.replace(/[^a-z0-9-]/gi, "_").toLowerCase()}-${Date.now()}.png`;
        await page!.screenshot({
          path: `${this.config.artifactsDir}/${filename}`,
          fullPage: true,
        });
        break;
      }

      case "api-call": {
        if (!apiRunner) throw new Error(`Step "${step.label}" requires api-runner but none provided`);
        if (!step.apiOptions) throw new Error(`Step "${step.label}" has type "api-call" but no apiOptions`);
        const response = await apiRunner.call(step.apiOptions);
        // Store response in state for subsequent steps to access
        ctx.state[`__apiResponse_${step.label}`] = response;
        break;
      }

      case "custom": {
        if (!step.handler) throw new Error(`Step "${step.label}" has type "custom" but no handler`);
        await step.handler(ctx);
        break;
      }

      default: {
        throw new Error(`Unknown step type: ${String((step as Step).type)}`);
      }
    }
  }

  // ─── Selector resolution ──────────────────────────────────────────────────

  /**
   * Resolves a selector key against the domain's SelectorMap.
   * Falls back to treating the value as a raw selector string.
   */
  private resolveSelector(selectorOrKey: string, ctx: StepContext, stepLabel: string): string {
    if (selectorOrKey in ctx.selectors) {
      return ctx.selectors[selectorOrKey] as string;
    }
    // Not in the map — treat as a raw selector (CSS/XPath)
    if (!selectorOrKey.startsWith("[") && !selectorOrKey.startsWith("#") &&
        !selectorOrKey.startsWith(".") && !selectorOrKey.startsWith("//") &&
        !selectorOrKey.includes(" ")) {
      console.warn(
        `[flow-engine] Step "${stepLabel}": selector key "${selectorOrKey}" not found in SelectorMap. ` +
          `Using as raw selector string. Add it to selectors.ts to suppress this warning.`
      );
    }
    return selectorOrKey;
  }

  // ─── Value interpolation ──────────────────────────────────────────────────

  /**
   * Resolves {{path.to.value}} tokens against ctx.state and ctx.config.
   * Logs a structured warning when a token resolves to undefined.
   * Token format: {{state.key}}, {{config.baseUrl}}, {{config.apiBaseUrl}}, etc.
   */
  private resolveValue(
    template: string,
    ctx: StepContext,
    stepLabel: string,
    fieldName: string
  ): string {
    return template.replace(/\{\{([^}]+)\}\}/g, (match, path: string) => {
      const trimmed = path.trim();
      const resolved = this.resolvePath(trimmed, ctx);

      if (resolved === undefined) {
        console.warn(
          `[flow-engine] Step "${stepLabel}" field "${fieldName}": ` +
            `interpolation token "{{${trimmed}}}" resolved to undefined. ` +
            `Check that ctx.state["${trimmed.replace(/^state\./, "")}"] is set by a previous step.`
        );
        return "";
      }

      return String(resolved);
    });
  }

  private resolvePath(dotPath: string, ctx: StepContext): unknown {
    const [root, ...rest] = dotPath.split(".");

    let base: unknown;
    if (root === "state") base = ctx.state;
    else if (root === "config") base = ctx.config;
    else base = ctx.state; // default root is state

    let current: unknown = base;
    const keys = root === "state" || root === "config" ? rest : [root, ...rest];

    for (const key of keys) {
      if (current === null || current === undefined) return undefined;
      current = (current as Record<string, unknown>)[key];
    }

    return current;
  }

  // ─── Guards ───────────────────────────────────────────────────────────────

  private requirePage(page: Page | undefined, stepType: string): asserts page is Page {
    if (!page) {
      throw new Error(
        `Step type "${stepType}" requires a browser page, but this journey is running in API mode.`
      );
    }
  }
}
