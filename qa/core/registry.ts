// ─────────────────────────────────────────────────────────────────────────────
// core/registry.ts
// In-memory registry of loaded Domain instances.
// Validates schemaVersion on registration and reports ghost/orphan domains.
// ─────────────────────────────────────────────────────────────────────────────

import { CURRENT_SCHEMA_VERSION, type Domain, type DomainManifest } from "./types.js";

export interface RegistryEntry {
  domain: Domain;
  loadedAt: string;
  schemaVersionMatch: boolean;
}

export interface RegistryDiagnostics {
  /** Domains in the manifest but missing from the filesystem. */
  ghostDomains: string[];
  /** Domain directories on disk but absent from the manifest. */
  orphanDomains: string[];
  /** Domains loaded but with a schemaVersion mismatch. */
  staleDomains: string[];
}

class DomainRegistry {
  private entries = new Map<string, RegistryEntry>();

  /**
   * Register a domain instance.
   * Warns when the domain's contract.schemaVersion does not match the runtime.
   */
  register(domain: Domain): void {
    const { name, schemaVersion } = domain.contract;
    const schemaVersionMatch = schemaVersion === CURRENT_SCHEMA_VERSION;

    if (!schemaVersionMatch) {
      const [currentMajor] = CURRENT_SCHEMA_VERSION.split(".");
      const [domainMajor] = (schemaVersion ?? "0").split(".");

      if (domainMajor !== currentMajor) {
        throw new Error(
          `Domain "${name}" has schemaVersion "${schemaVersion}" which is incompatible ` +
            `with runtime "${CURRENT_SCHEMA_VERSION}". Major version mismatch — ` +
            `re-generate this domain with the current skill version.`
        );
      }

      console.warn(
        `[registry] Domain "${name}" schemaVersion "${schemaVersion}" differs from ` +
          `runtime "${CURRENT_SCHEMA_VERSION}". Run "qa:validate" to inspect.`
      );
    }

    this.entries.set(name, {
      domain,
      loadedAt: new Date().toISOString(),
      schemaVersionMatch,
    });
  }

  get(name: string): Domain | undefined {
    return this.entries.get(name)?.domain;
  }

  getAll(): Domain[] {
    return [...this.entries.values()].map((e) => e.domain);
  }

  has(name: string): boolean {
    return this.entries.has(name);
  }

  clear(): void {
    this.entries.clear();
  }

  /**
   * Cross-references the registry against the manifest to find
   * ghost domains (in manifest, not loaded) and orphan domains
   * (loaded, not in manifest).
   */
  getDiagnostics(manifest: DomainManifest): RegistryDiagnostics {
    const manifestNames = new Set(Object.keys(manifest.domains));
    const registryNames = new Set(this.entries.keys());

    const ghostDomains = [...manifestNames].filter((n) => !registryNames.has(n));
    const orphanDomains = [...registryNames].filter((n) => !manifestNames.has(n));
    const staleDomains = [...this.entries.entries()]
      .filter(([, entry]) => !entry.schemaVersionMatch)
      .map(([name]) => name);

    return { ghostDomains, orphanDomains, staleDomains };
  }
}

/** Singleton registry. Import and use throughout the platform. */
export const registry = new DomainRegistry();
