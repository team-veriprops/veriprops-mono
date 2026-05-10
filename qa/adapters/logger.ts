// ─────────────────────────────────────────────────────────────────────────────
// adapters/logger.ts
// Loads QAConfig from environment variables (with .env fallback).
// Provides a structured Logger class.
// Subscribes to the event bus to print live run progress.
// ─────────────────────────────────────────────────────────────────────────────

import fs from "node:fs";
import path from "node:path";
import { eventBus } from "../core/event-bus.js";
import type { QAConfig } from "../core/types.js";

// ─── Env loader ───────────────────────────────────────────────────────────────

function loadEnvFile(): void {
  const envPath = path.resolve(process.cwd(), ".env");
  if (!fs.existsSync(envPath)) return;

  const lines = fs.readFileSync(envPath, "utf-8").split("\n");
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;

    const eqIndex = trimmed.indexOf("=");
    if (eqIndex === -1) continue;

    const key = trimmed.slice(0, eqIndex).trim();
    const value = trimmed.slice(eqIndex + 1).trim().replace(/^["']|["']$/g, "");

    // Env vars take precedence over .env file
    if (!(key in process.env)) {
      process.env[key] = value;
    }
  }
}

function env(key: string, fallback?: string): string {
  const value = process.env[key] ?? fallback;
  if (value === undefined) {
    throw new Error(
      `Required environment variable "${key}" is not set. ` +
        `Copy qa/.env.example to qa/.env and fill in the values.`
    );
  }
  return value;
}

function envOptional(key: string, fallback?: string): string | undefined {
  return process.env[key] ?? fallback;
}

function envInt(key: string, fallback: number): number {
  const raw = process.env[key];
  if (!raw) return fallback;
  const parsed = parseInt(raw, 10);
  return isNaN(parsed) ? fallback : parsed;
}

function envBool(key: string, fallback: boolean): boolean {
  const raw = process.env[key];
  if (!raw) return fallback;
  return raw.toLowerCase() === "true" || raw === "1";
}

// ─── Config loader ────────────────────────────────────────────────────────────

let _config: QAConfig | null = null;

export function loadConfig(): QAConfig {
  if (_config) return _config;

  loadEnvFile();

  const environment = (envOptional("ENVIRONMENT", "local") ?? "local") as QAConfig["environment"];
  const otpMode = (envOptional("OTP_MODE", "mailpit") ?? "mailpit") as QAConfig["otpMode"];
  const appReadySelector = envOptional("APP_READY_SELECTOR");

  _config = {
    environment,
    baseUrl: env("BASE_URL", "http://localhost:3000"),
    apiBaseUrl: env("API_BASE_URL", "http://localhost:8000"),
    mailpitUrl: env("MAILPIT_URL", "http://localhost:8025"),
    otpMode,
    testOtp: envOptional("TEST_OTP", "123456") ?? "123456",
    headless: envBool("HEADLESS", true),
    appReadySelector: appReadySelector || undefined,
    timeout: envInt("TIMEOUT", 30000),
    retries: envInt("RETRIES", 1),
    artifactsDir: path.resolve(process.cwd(), envOptional("ARTIFACTS_DIR", "./artifacts") ?? "./artifacts"),
    maxRuns: envInt("MAX_RUNS", 20),
    cacheTtl: envInt("CACHE_TTL", 3600),
  };

  return _config;
}

/** Reset the cached config — used in tests or after env changes. */
export function resetConfig(): void {
  _config = null;
}

// ─── Logger ───────────────────────────────────────────────────────────────────

type LogLevel = "info" | "warn" | "error" | "debug";

export class Logger {
  private prefix: string;
  private debugEnabled: boolean;

  constructor(prefix: string) {
    this.prefix = prefix;
    this.debugEnabled = process.env["QA_DEBUG"] === "true" || process.env["QA_DEBUG"] === "1";
  }

  info(message: string, ...args: unknown[]): void {
    console.log(`[${this.prefix}] ${message}`, ...args);
  }

  warn(message: string, ...args: unknown[]): void {
    console.warn(`[${this.prefix}] ⚠ ${message}`, ...args);
  }

  error(message: string, ...args: unknown[]): void {
    console.error(`[${this.prefix}] ✗ ${message}`, ...args);
  }

  debug(message: string, ...args: unknown[]): void {
    if (this.debugEnabled) {
      console.debug(`[${this.prefix}] ${message}`, ...args);
    }
  }
}

// ─── Event bus progress subscriber ───────────────────────────────────────────

/**
 * Subscribes to the event bus and prints live run progress.
 * Call once at CLI startup. Returns an unsubscribe function.
 */
export function attachProgressLogger(): () => void {
  const unsubDomainStart = eventBus.on("domain:start", (event) => {
    console.log(`\n  ▶  ${event.payload.domainName}`);
  });

  const unsubJourneyEnd = eventBus.on("journey:end", (event) => {
    const { result } = event.payload;
    const icon =
      result.status === "pass" ? "✅" :
      result.status === "fail" ? "❌" :
      result.status === "skip" ? "⏭ " : "⚠️ ";
    console.log(`       ${icon}  ${result.journeyName} (${result.durationMs}ms)`);
  });

  const unsubStepFail = eventBus.on("step:fail", (event) => {
    console.error(`          ✗ ${event.payload.label}: ${event.payload.error}`);
  });

  const unsubCacheHit = eventBus.on("cache:hit", (event) => {
    console.log(`  ⚡ Cache hit — skipping: ${event.payload.stepLabel}`);
  });

  return () => {
    unsubDomainStart();
    unsubJourneyEnd();
    unsubStepFail();
    unsubCacheHit();
  };
}
