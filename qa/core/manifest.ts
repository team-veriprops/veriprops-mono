// ─────────────────────────────────────────────────────────────────────────────
// core/manifest.ts
// Reads and writes domain-manifest.json.
// Validates schemaVersion on load and warns when the manifest is stale.
// ─────────────────────────────────────────────────────────────────────────────

import fs from "node:fs";
import path from "node:path";
import {
  CURRENT_SCHEMA_VERSION,
  type DomainManifest,
  type ManifestDomainEntry,
  type SchemaVersion,
} from "./types.js";

export const manifestPath = path.resolve(process.cwd(), "domain-manifest.json");

// ─── Load ─────────────────────────────────────────────────────────────────────

export function loadManifest(): DomainManifest {
  if (!fs.existsSync(manifestPath)) {
    return createEmptyManifest();
  }

  const raw = fs.readFileSync(manifestPath, "utf-8");
  let parsed: unknown;

  try {
    parsed = JSON.parse(raw);
  } catch {
    throw new Error(`domain-manifest.json is not valid JSON. Run "qa:validate --fix" to repair.`);
  }

  const manifest = parsed as DomainManifest;

  // Schema version check — warn but do not throw on minor mismatch
  if (!manifest.schemaVersion) {
    console.warn(
      `[manifest] Warning: domain-manifest.json has no schemaVersion. ` +
        `Expected "${CURRENT_SCHEMA_VERSION}". Run "qa:validate" to inspect domains.`
    );
  } else if (manifest.schemaVersion !== CURRENT_SCHEMA_VERSION) {
    const [currentMajor] = CURRENT_SCHEMA_VERSION.split(".");
    const [manifestMajor] = manifest.schemaVersion.split(".");

    if (manifestMajor !== currentMajor) {
      throw new Error(
        `domain-manifest.json schemaVersion "${manifest.schemaVersion}" is incompatible ` +
          `with runtime version "${CURRENT_SCHEMA_VERSION}". ` +
          `Major version mismatch — manual migration required.`
      );
    }

    console.warn(
      `[manifest] Warning: domain-manifest.json schemaVersion "${manifest.schemaVersion}" ` +
        `differs from runtime "${CURRENT_SCHEMA_VERSION}". Consider running "qa:validate".`
    );
  }

  return manifest;
}

// ─── Save ─────────────────────────────────────────────────────────────────────

export function saveManifest(manifest: DomainManifest): void {
  const updated: DomainManifest = {
    ...manifest,
    schemaVersion: CURRENT_SCHEMA_VERSION,
    updatedAt: new Date().toISOString(),
  };
  fs.writeFileSync(manifestPath, JSON.stringify(updated, null, 2) + "\n", "utf-8");
}

// ─── Factory ──────────────────────────────────────────────────────────────────

export function createEmptyManifest(): DomainManifest {
  return {
    schemaVersion: CURRENT_SCHEMA_VERSION,
    updatedAt: new Date().toISOString(),
    domains: {},
  };
}

// ─── Domain operations ───────────────────────────────────────────────────────

export function addDomain(
  manifest: DomainManifest,
  entry: Omit<ManifestDomainEntry, "addedAt" | "updatedAt" | "schemaVersion">
): DomainManifest {
  const now = new Date().toISOString();
  return {
    ...manifest,
    domains: {
      ...manifest.domains,
      [entry.name]: {
        ...entry,
        schemaVersion: CURRENT_SCHEMA_VERSION as SchemaVersion,
        addedAt: now,
        updatedAt: now,
      },
    },
  };
}

export function removeDomain(manifest: DomainManifest, name: string): DomainManifest {
  const { [name]: _removed, ...rest } = manifest.domains;
  return { ...manifest, domains: rest };
}

export function enableDomain(manifest: DomainManifest, name: string): DomainManifest {
  return updateDomainEntry(manifest, name, { enabled: true });
}

export function disableDomain(manifest: DomainManifest, name: string): DomainManifest {
  return updateDomainEntry(manifest, name, { enabled: false });
}

export function getDomain(
  manifest: DomainManifest,
  name: string
): ManifestDomainEntry | undefined {
  return manifest.domains[name];
}

export function getEnabledDomains(manifest: DomainManifest): ManifestDomainEntry[] {
  return Object.values(manifest.domains).filter((d) => d.enabled);
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function updateDomainEntry(
  manifest: DomainManifest,
  name: string,
  patch: Partial<ManifestDomainEntry>
): DomainManifest {
  const existing = manifest.domains[name];
  if (!existing) {
    throw new Error(`Domain "${name}" not found in manifest.`);
  }
  return {
    ...manifest,
    domains: {
      ...manifest.domains,
      [name]: { ...existing, ...patch, updatedAt: new Date().toISOString() },
    },
  };
}
