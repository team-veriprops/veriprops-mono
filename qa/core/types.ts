// ─────────────────────────────────────────────────────────────────────────────
// core/types.ts
// Single source of truth for all QA platform types.
// Domain authors import from here. Runtime imports from here.
// The skill reads this file when generating new domains.
// ─────────────────────────────────────────────────────────────────────────────

export const CURRENT_SCHEMA_VERSION = "1.0.0" as const;
export type SchemaVersion = typeof CURRENT_SCHEMA_VERSION;

// ─── Configuration ───────────────────────────────────────────────────────────

export interface QAConfig {
  environment: "local" | "ci" | "staging";
  baseUrl: string;
  apiBaseUrl: string;
  mailpitUrl: string;
  otpMode: "mailpit" | "static";
  testOtp: string;
  headless: boolean;
  /** CSS selector fallback if window.__app_ready is not set by the frontend. */
  appReadySelector?: string;
  timeout: number;
  retries: number;
  artifactsDir: string;
  /** Number of run artifact directories to retain. Oldest pruned on each run. */
  maxRuns: number;
  /** TTL in seconds for idempotent bootstrap step cache entries. */
  cacheTtl: number;
}

// ─── Bootstrap ───────────────────────────────────────────────────────────────

export interface BootstrapStep {
  /** Human-readable label shown in logs. */
  label: string;
  /**
   * Backend adapter method to call: "reset" | "seed" | "bootstrap" | custom.
   * The runner resolves this against the BackendAdapter at runtime.
   */
  action: "reset" | "seed" | "bootstrap" | string;
  /** Optional payload forwarded to the backend endpoint. */
  payload?: Record<string, unknown>;
  /**
   * When true, the runner checks the step cache before executing.
   * If a matching cache entry exists and is within CACHE_TTL, the step is skipped.
   * Only set this on steps that are safe to skip (idempotent data seeding etc).
   */
  idempotent?: boolean;
}

// ─── Session Fixtures ────────────────────────────────────────────────────────

export interface SessionFixture {
  /** Unique key for this session (e.g. "adminUser", "customerUser"). */
  key: string;
  /** Steps that must run before this session is considered ready. */
  bootstrap: BootstrapStep[];
  /** Optional teardown steps that run after all journeys for this domain complete. */
  teardown?: BootstrapStep[];
}

export interface DomainFixtures {
  sessions: SessionFixture[];
}

// ─── Selectors ───────────────────────────────────────────────────────────────

/**
 * Flat map of selector keys to CSS/XPath selector strings.
 * Centralised here so journeys never contain raw selector strings.
 */
export type SelectorMap = Record<string, string>;

// ─── Assertions ──────────────────────────────────────────────────────────────

export type AssertionStatus = "pass" | "fail" | "skip";

export interface AssertionResult {
  status: AssertionStatus;
  message: string;
  actual?: unknown;
  expected?: unknown;
}

// ─── Steps ───────────────────────────────────────────────────────────────────

export type StepType =
  | "navigate"
  | "click"
  | "fill"
  | "select"
  | "wait"
  | "wait-for-selector"
  | "wait-for-network"
  | "assert"
  | "screenshot"
  | "api-call"
  | "custom";

export interface StepContext {
  /** Resolved config for the current run. */
  config: QAConfig;
  /** Shared state bag — steps can read/write arbitrary values here. */
  state: Record<string, unknown>;
  /** Selectors map from the domain's selectors.ts. */
  selectors: SelectorMap;
  /** Current session key declared by the journey. */
  sessionKey?: string;
}

export interface Step {
  type: StepType;
  label: string;
  /**
   * Selector key (looked up in SelectorMap) or raw selector string.
   * Supports {{state.path}} interpolation.
   */
  selector?: string;
  /** Value to fill/select. Supports {{state.path}} interpolation. */
  value?: string;
  /** URL to navigate to. Supports {{config.baseUrl}} interpolation. */
  url?: string;
  /** Assertion to run (used when type = "assert"). */
  assertion?: () => AssertionResult | Promise<AssertionResult>;
  /** API call options (used when type = "api-call"). */
  apiOptions?: APIRequestOptions;
  /** Custom step handler (used when type = "custom"). */
  handler?: (ctx: StepContext) => Promise<void>;
  /** Duration in ms for type = "wait". */
  duration?: number;
  /** When true, a failure here does not cascade to subsequent steps. */
  optional?: boolean;
}

// ─── Journeys ────────────────────────────────────────────────────────────────

export type JourneyMode = "browser" | "api";

export interface Journey {
  name: string;
  mode: JourneyMode;
  /** Session key from DomainFixtures.sessions this journey runs under. */
  sessionKey?: string;
  steps: Step[];
  /** When true, skip this journey and mark it as skipped in the report. */
  skip?: boolean;
}

export type JourneyStatus = "pass" | "fail" | "skip" | "error";

export interface JourneyResult {
  journeyName: string;
  status: JourneyStatus;
  steps: StepResult[];
  durationMs: number;
  error?: string;
}

export interface StepResult {
  label: string;
  type: StepType;
  status: "pass" | "fail" | "skip";
  durationMs: number;
  assertion?: AssertionResult;
  error?: string;
}

// ─── Domain ──────────────────────────────────────────────────────────────────

/**
 * The shape every generated domain/index.ts must export as default.
 * The skill SKILL.md uses this as its canonical reference.
 */
export interface Domain {
  contract: DomainContract;
  fixtures: DomainFixtures;
  selectors: SelectorMap;
  journeys: Journey[];
  assertions: Record<string, () => AssertionResult | Promise<AssertionResult>>;
}

export interface DomainContract {
  /** Must match CURRENT_SCHEMA_VERSION. Validated by registry on load. */
  schemaVersion: SchemaVersion;
  /** Unique machine-readable domain identifier (kebab-case). */
  name: string;
  /** Human-readable description shown in reports and logs. */
  description: string;
  /**
   * Domain names (by contract.name) that must complete before this domain runs.
   * The orchestrator performs a topological sort. Circular deps are rejected.
   */
  dependsOn?: string[];
  /**
   * Regex pattern string to extract OTP from email body.
   * Overrides the default pattern in MailpitAdapter.extractOTP.
   * Example: "Your code is (\\d{6})"
   */
  otpPattern?: string;
  /**
   * Override the global appReadySelector for this domain's browser journeys.
   * Falls back to QAConfig.appReadySelector, then window.__app_ready.
   */
  appReadySelector?: string;
  tags?: string[];
  owner?: string;
}

export type DomainRunStatus = "pass" | "fail" | "partial" | "error" | "skipped";

export interface DomainRunResult {
  domainName: string;
  status: DomainRunStatus;
  journeys: JourneyResult[];
  durationMs: number;
  artifactPath?: string;
  error?: string;
}

// ─── Run Report ───────────────────────────────────────────────────────────────

export interface RunReport {
  runId: string;
  startedAt: string;
  completedAt: string;
  durationMs: number;
  status: "pass" | "fail" | "partial";
  environment: string;
  domains: DomainRunResult[];
  summary: RunSummary;
}

export interface RunSummary {
  total: number;
  passed: number;
  failed: number;
  partial: number;
  skipped: number;
  errors: number;
}

// ─── Manifest ────────────────────────────────────────────────────────────────

export interface ManifestDomainEntry {
  name: string;
  path: string;
  enabled: boolean;
  schemaVersion: SchemaVersion;
  addedAt: string;
  updatedAt: string;
  tags?: string[];
  owner?: string;
  dependsOn?: string[];
}

export interface DomainManifest {
  schemaVersion: SchemaVersion;
  updatedAt: string;
  domains: Record<string, ManifestDomainEntry>;
}

// ─── API ─────────────────────────────────────────────────────────────────────

export type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

export interface APIRequestOptions {
  method: HttpMethod;
  path: string;
  body?: unknown;
  headers?: Record<string, string>;
  rawResponse?: boolean;
}

export interface APIResponse<T = unknown> {
  status: number;
  headers: Record<string, string>;
  body: T;
  ok: boolean;
}

// ─── Forensic ────────────────────────────────────────────────────────────────

export interface ForensicSnapshot {
  timestamp: string;
  screenshotPath?: string;
  domPath?: string;
  jsonPath?: string;
  logPath?: string;
}

export interface ForensicArtifacts {
  runId: string;
  domainName: string;
  journeyName: string;
  snapshots: ForensicSnapshot[];
}

// ─── Validation ──────────────────────────────────────────────────────────────

export type ValidationSeverity = "error" | "warning" | "info";

export interface ValidationIssue {
  severity: ValidationSeverity;
  domain?: string;
  field?: string;
  message: string;
  fixable: boolean;
}

export interface ValidationResult {
  valid: boolean;
  issues: ValidationIssue[];
}

export interface DriftReport {
  domainName: string;
  schemaVersion: string;
  currentVersion: string;
  driftedFields: string[];
  ghostDomains: string[];
  orphanDomains: string[];
}

// ─── Events ──────────────────────────────────────────────────────────────────

export type QAEventType =
  | "run:start"
  | "run:complete"
  | "domain:start"
  | "domain:end"
  | "journey:start"
  | "journey:end"
  | "step:pass"
  | "step:fail"
  | "step:skip"
  | "preflight:pass"
  | "preflight:fail"
  | "cache:hit"
  | "cache:miss";

export interface QAEventPayload {
  "run:start": { runId: string; domains: string[] };
  "run:complete": { runId: string; report: RunReport };
  "domain:start": { runId: string; domainName: string };
  "domain:end": { runId: string; domainName: string; result: DomainRunResult };
  "journey:start": { runId: string; domainName: string; journeyName: string };
  "journey:end": { runId: string; domainName: string; result: JourneyResult };
  "step:pass": { runId: string; domainName: string; label: string; durationMs: number };
  "step:fail": { runId: string; domainName: string; label: string; error: string };
  "step:skip": { runId: string; domainName: string; label: string };
  "preflight:pass": { runId: string; domainsChecked: number };
  "preflight:fail": { runId: string; issues: ValidationIssue[] };
  "cache:hit": { stepLabel: string; domainName: string };
  "cache:miss": { stepLabel: string; domainName: string };
}

export type QAEvent<T extends QAEventType = QAEventType> = {
  type: T;
  timestamp: string;
  payload: QAEventPayload[T];
};
