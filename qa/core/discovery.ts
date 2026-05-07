// ─────────────────────────────────────────────────────────────────────────────
// core/discovery.ts
// Discovers domain directories, dynamically imports domain modules,
// validates their shape, and registers them in the registry.
// ─────────────────────────────────────────────────────────────────────────────

import fs from "node:fs";
import path from "node:path";
import { registry } from "./registry.js";
import type { Domain, DomainManifest, ManifestDomainEntry } from "./types.js";

const DOMAINS_DIR = path.resolve(process.cwd(), "domains");

// ─── Discovery ───────────────────────────────────────────────────────────────

/**
 * Discovers and loads all enabled domains from the manifest.
 * Skips disabled domains and logs warnings for load failures.
 */
export async function discoverDomains(manifest: DomainManifest): Promise<void> {
  registry.clear();

  const enabled = Object.values(manifest.domains).filter((d) => d.enabled);

  if (enabled.length === 0) {
    console.warn("[discovery] No enabled domains found in manifest.");
    return;
  }

  const results = await Promise.allSettled(
    enabled.map((entry) => importDomain(entry))
  );

  for (const result of results) {
    if (result.status === "rejected") {
      console.error(`[discovery] Failed to load domain:`, result.reason);
    }
  }
}

/**
 * Imports a single domain module by its manifest entry.
 * Validates shape and registers it in the registry.
 */
export async function importDomain(entry: ManifestDomainEntry): Promise<void> {
  const domainPath = path.resolve(process.cwd(), entry.path, "index.ts");

  if (!fs.existsSync(domainPath)) {
    throw new Error(
      `Domain "${entry.name}" declared in manifest but index.ts not found at: ${domainPath}`
    );
  }

  let mod: unknown;
  try {
    mod = await import(domainPath);
  } catch (err) {
    throw new Error(`Domain "${entry.name}" failed to import: ${String(err)}`);
  }

  const domain = (mod as { default?: unknown }).default;

  const validation = validateDomainShape(domain, entry.name);
  if (!validation.valid) {
    throw new Error(
      `Domain "${entry.name}" failed shape validation:\n` +
        validation.errors.map((e) => `  - ${e}`).join("\n")
    );
  }

  registry.register(domain as Domain);
}

// ─── Filesystem Scan ─────────────────────────────────────────────────────────

/**
 * Scans the domains/ directory for subdirectories containing an index.ts.
 * Returns the domain names found on disk (regardless of manifest state).
 * Used by the validate command to detect orphan domains.
 */
export function scanDomainDirectories(): string[] {
  if (!fs.existsSync(DOMAINS_DIR)) return [];

  return fs
    .readdirSync(DOMAINS_DIR, { withFileTypes: true })
    .filter(
      (entry) =>
        entry.isDirectory() &&
        fs.existsSync(path.join(DOMAINS_DIR, entry.name, "index.ts"))
    )
    .map((entry) => entry.name);
}

// ─── Shape Validation ─────────────────────────────────────────────────────────

interface ShapeValidation {
  valid: boolean;
  errors: string[];
}

/**
 * Validates that a loaded module export conforms to the Domain interface.
 * Checks required top-level keys and contract fields.
 * Does not validate deep journey/step structure — that is the role of the
 * flow engine at runtime.
 */
export function validateDomainShape(value: unknown, domainName: string): ShapeValidation {
  const errors: string[] = [];

  if (typeof value !== "object" || value === null) {
    return { valid: false, errors: [`Default export must be an object, got ${typeof value}`] };
  }

  const domain = value as Record<string, unknown>;

  // Required top-level keys
  for (const key of ["contract", "fixtures", "selectors", "journeys", "assertions"]) {
    if (!(key in domain)) {
      errors.push(`Missing required export key: "${key}"`);
    }
  }

  // Contract shape
  if (domain["contract"] && typeof domain["contract"] === "object") {
    const contract = domain["contract"] as Record<string, unknown>;
    for (const field of ["schemaVersion", "name", "description"]) {
      if (!contract[field]) {
        errors.push(`contract.${field} is required`);
      }
    }

    // name must match the directory / manifest entry
    if (contract["name"] && contract["name"] !== domainName) {
      errors.push(
        `contract.name "${String(contract["name"])}" does not match manifest entry "${domainName}"`
      );
    }
  }

  // journeys must be an array
  if ("journeys" in domain && !Array.isArray(domain["journeys"])) {
    errors.push(`journeys must be an array`);
  }

  // assertions must be an object
  if ("assertions" in domain && typeof domain["assertions"] !== "object") {
    errors.push(`assertions must be an object`);
  }

  return { valid: errors.length === 0, errors };
}
