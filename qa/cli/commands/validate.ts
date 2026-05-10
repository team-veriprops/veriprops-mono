// ─────────────────────────────────────────────────────────────────────────────
// cli/commands/validate.ts
// Validates all domains: shape, schema versions, dependency cycles,
// ghost/orphan detection. Optionally auto-repairs fixable issues.
// ─────────────────────────────────────────────────────────────────────────────

import { loadConfig, Logger } from "../../adapters/logger.js";
import { loadManifest, saveManifest, removeDomain, addDomain } from "../../core/manifest.js";
import { discoverDomains, scanDomainDirectories, validateDomainShape } from "../../core/discovery.js";
import { registry } from "../../core/registry.js";
import { topologicalSort, formatSortDiagnostics, type GraphNode } from "../../core/dependency-graph.js";
import { CURRENT_SCHEMA_VERSION } from "../../core/types.js";
import type { ValidationIssue } from "../../core/types.js";

const logger = new Logger("validate");

interface ValidateOptions {
  fix?: boolean;
  domain?: string;
}

export async function validateCommand(options: ValidateOptions): Promise<void> {
  const config = loadConfig();
  const manifest = loadManifest();
  const issues: ValidationIssue[] = [];

  logger.info("Validating QA platform...\n");

  // ── Discover and load domains ─────────────────────────────────────────────
  await discoverDomains(manifest);
  const allDomains = registry.getAll();

  const domains = options.domain
    ? allDomains.filter((d) => d.contract.name === options.domain)
    : allDomains;

  if (options.domain && domains.length === 0) {
    logger.error(`Domain "${options.domain}" not found in registry.`);
    process.exit(1);
  }

  // ── 1. Domain shape validation ────────────────────────────────────────────
  logger.info("1. Shape validation");
  for (const domain of domains) {
    const result = validateDomainShape(domain, domain.contract.name);
    if (!result.valid) {
      for (const err of result.errors) {
        issues.push({
          severity: "error",
          domain: domain.contract.name,
          message: err,
          fixable: false,
        });
      }
      logger.error(`   ✗ ${domain.contract.name}: shape invalid`);
    } else {
      logger.info(`   ✅ ${domain.contract.name}`);
    }
  }

  // ── 2. Schema version check ───────────────────────────────────────────────
  logger.info("\n2. Schema version check");
  for (const domain of domains) {
    const { name, schemaVersion } = domain.contract;
    if (schemaVersion === CURRENT_SCHEMA_VERSION) {
      logger.info(`   ✅ ${name} (${schemaVersion})`);
    } else {
      const [curMajor] = CURRENT_SCHEMA_VERSION.split(".");
      const [domMajor] = (schemaVersion ?? "0").split(".");
      const severity = domMajor !== curMajor ? "error" : "warning";
      issues.push({
        severity,
        domain: name,
        field: "contract.schemaVersion",
        message: `"${name}" schemaVersion "${schemaVersion ?? "none"}" vs runtime "${CURRENT_SCHEMA_VERSION}"`,
        fixable: false,
      });
      const icon = severity === "error" ? "✗" : "⚠";
      logger.warn(`   ${icon} ${name}: ${schemaVersion ?? "missing"} → ${CURRENT_SCHEMA_VERSION}`);
    }
  }

  // ── 3. Dependency cycle detection ─────────────────────────────────────────
  logger.info("\n3. Dependency graph");
  const nodes: GraphNode[] = domains.map((d) => ({
    name: d.contract.name,
    dependsOn: d.contract.dependsOn ?? [],
  }));
  const sortResult = topologicalSort(nodes);

  if (sortResult.ok) {
    logger.info(`   ✅ No cycles detected`);
    logger.info(`   Execution order: ${sortResult.order.join(" → ")}`);
  } else {
    const diagnostics = formatSortDiagnostics(sortResult);
    for (const line of diagnostics) {
      logger.error(`   ${line}`);
      issues.push({ severity: "error", field: "dependsOn", message: line, fixable: false });
    }
  }

  if (sortResult.missing.length > 0) {
    for (const m of sortResult.missing) {
      logger.warn(`   ⚠ Missing dep: ${m}`);
      issues.push({ severity: "warning", field: "dependsOn", message: `Missing dep: ${m}`, fixable: false });
    }
  }

  // ── 4. Ghost and orphan detection ─────────────────────────────────────────
  logger.info("\n4. Ghost / orphan detection");
  const diagnostics = registry.getDiagnostics(manifest);

  if (diagnostics.ghostDomains.length === 0 && diagnostics.orphanDomains.length === 0) {
    logger.info("   ✅ No ghost or orphan domains");
  }

  for (const name of diagnostics.ghostDomains) {
    const issue: ValidationIssue = {
      severity: "warning",
      domain: name,
      message: `Ghost domain: "${name}" is in manifest but not loadable from disk`,
      fixable: true,
    };
    issues.push(issue);
    logger.warn(`   ⚠ Ghost: ${name}`);
  }

  for (const name of diagnostics.orphanDomains) {
    const issue: ValidationIssue = {
      severity: "warning",
      domain: name,
      message: `Orphan domain: "${name}" exists on disk but is not in manifest`,
      fixable: true,
    };
    issues.push(issue);
    logger.warn(`   ⚠ Orphan: ${name}`);
  }

  // ── 5. Filesystem scan for unregistered domain directories ────────────────
  const diskDomains = scanDomainDirectories();
  const manifestNames = new Set(Object.keys(manifest.domains));
  for (const name of diskDomains) {
    if (!manifestNames.has(name)) {
      issues.push({
        severity: "warning",
        domain: name,
        message: `Domain directory "domains/${name}" exists but is not in manifest. Run "add-domain" to register it.`,
        fixable: false,
      });
      logger.warn(`   ⚠ Unregistered directory: domains/${name}`);
    }
  }

  // ── Auto-fix ──────────────────────────────────────────────────────────────
  if (options.fix) {
    logger.info("\n5. Auto-repair (--fix)");
    let updatedManifest = manifest;
    let fixed = 0;

    // Remove ghost domains from manifest
    for (const name of diagnostics.ghostDomains) {
      updatedManifest = removeDomain(updatedManifest, name);
      logger.info(`   ✅ Removed ghost domain "${name}" from manifest`);
      fixed++;
    }

    // Add orphan domains to manifest
    for (const name of diagnostics.orphanDomains) {
      const domain = registry.get(name);
      if (domain) {
        updatedManifest = addDomain(updatedManifest, {
          name,
          path: `domains/${name}`,
          enabled: false,
          tags: domain.contract.tags,
          owner: domain.contract.owner,
          dependsOn: domain.contract.dependsOn,
        });
        logger.info(`   ✅ Added orphan domain "${name}" to manifest (disabled)`);
        fixed++;
      }
    }

    if (fixed > 0) {
      saveManifest(updatedManifest);
      logger.info(`\n   Manifest updated. ${fixed} issue(s) repaired.`);
    } else {
      logger.info("   No fixable issues found.");
    }
  }

  // ── Summary ───────────────────────────────────────────────────────────────
  const errors = issues.filter((i) => i.severity === "error");
  const warnings = issues.filter((i) => i.severity === "warning");

  console.log("\n─────────────────────────────────────────");
  if (errors.length === 0 && warnings.length === 0) {
    console.log("  ✅ All checks passed");
  } else {
    console.log(`  ✗  ${errors.length} error(s)   ⚠  ${warnings.length} warning(s)`);
    if (!options.fix && issues.some((i) => i.fixable)) {
      console.log('  Run with --fix to auto-repair fixable issues.');
    }
  }
  console.log("─────────────────────────────────────────\n");

  process.exit(errors.length > 0 ? 1 : 0);
}
