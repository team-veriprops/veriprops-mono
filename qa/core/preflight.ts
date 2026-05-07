// ─────────────────────────────────────────────────────────────────────────────
// core/preflight.ts
// Lightweight pre-flight check that runs before every suite execution.
// Catches shape errors, schema mismatches, missing env vars, and dep cycles
// before any browser or API call is made.
// ─────────────────────────────────────────────────────────────────────────────

import type {
  Domain,
  DomainManifest,
  QAConfig,
  ValidationIssue,
  ValidationResult,
} from "./types.js";
import { CURRENT_SCHEMA_VERSION } from "./types.js";
import { topologicalSort, type GraphNode } from "./dependency-graph.js";

// ─── Required env vars ────────────────────────────────────────────────────────

const REQUIRED_ENV_VARS: Array<{ key: keyof QAConfig; label: string }> = [
  { key: "baseUrl", label: "BASE_URL" },
  { key: "apiBaseUrl", label: "API_BASE_URL" },
  { key: "mailpitUrl", label: "MAILPIT_URL" },
];

// ─── Pre-flight runner ────────────────────────────────────────────────────────

export async function runPreflight(
  config: QAConfig,
  manifest: DomainManifest,
  domains: Domain[]
): Promise<ValidationResult> {
  const issues: ValidationIssue[] = [];

  // ── 1. Required environment variables ─────────────────────────────────────
  for (const { key, label } of REQUIRED_ENV_VARS) {
    const value = config[key];
    if (!value || (typeof value === "string" && value.trim() === "")) {
      issues.push({
        severity: "error",
        field: label,
        message: `Required environment variable ${label} is not set.`,
        fixable: false,
      });
    }
  }

  // ── 2. Schema version check per domain ────────────────────────────────────
  for (const domain of domains) {
    const { name, schemaVersion } = domain.contract;

    if (!schemaVersion) {
      issues.push({
        severity: "error",
        domain: name,
        field: "contract.schemaVersion",
        message: `Domain "${name}" is missing contract.schemaVersion. Re-generate with the current skill.`,
        fixable: false,
      });
      continue;
    }

    if (schemaVersion !== CURRENT_SCHEMA_VERSION) {
      const [curMajor] = CURRENT_SCHEMA_VERSION.split(".");
      const [domMajor] = schemaVersion.split(".");

      if (domMajor !== curMajor) {
        issues.push({
          severity: "error",
          domain: name,
          field: "contract.schemaVersion",
          message:
            `Domain "${name}" schemaVersion "${schemaVersion}" is incompatible with ` +
            `runtime "${CURRENT_SCHEMA_VERSION}" (major version mismatch). Re-generate this domain.`,
          fixable: false,
        });
      } else {
        issues.push({
          severity: "warning",
          domain: name,
          field: "contract.schemaVersion",
          message:
            `Domain "${name}" schemaVersion "${schemaVersion}" differs from ` +
            `runtime "${CURRENT_SCHEMA_VERSION}". Consider upgrading with "add-domain --upgrade".`,
          fixable: true,
        });
      }
    }
  }

  // ── 3. Dependency graph check ─────────────────────────────────────────────
  const nodes: GraphNode[] = domains.map((d) => ({
    name: d.contract.name,
    dependsOn: d.contract.dependsOn ?? [],
  }));

  const sortResult = topologicalSort(nodes);

  if (!sortResult.ok && sortResult.cycle) {
    issues.push({
      severity: "error",
      field: "dependsOn",
      message: `Circular dependency detected: ${sortResult.cycle.join(" → ")}`,
      fixable: false,
    });
  }

  for (const missing of sortResult.missing) {
    issues.push({
      severity: "warning",
      field: "dependsOn",
      message: `Missing dependency reference: ${missing}`,
      fixable: false,
    });
  }

  // ── 4. Ghost domain check (in manifest, not loaded) ───────────────────────
  const loadedNames = new Set(domains.map((d) => d.contract.name));
  for (const [name, entry] of Object.entries(manifest.domains)) {
    if (entry.enabled && !loadedNames.has(name)) {
      issues.push({
        severity: "warning",
        domain: name,
        message: `Domain "${name}" is enabled in manifest but was not loaded. Check the path: ${entry.path}`,
        fixable: false,
      });
    }
  }

  // ── 5. Domain name / manifest key consistency ─────────────────────────────
  for (const domain of domains) {
    const { name } = domain.contract;
    const manifestEntry = manifest.domains[name];
    if (manifestEntry && manifestEntry.name !== name) {
      issues.push({
        severity: "error",
        domain: name,
        message: `Manifest key "${manifestEntry.name}" does not match contract.name "${name}".`,
        fixable: true,
      });
    }
  }

  const valid = !issues.some((i) => i.severity === "error");
  return { valid, issues };
}
