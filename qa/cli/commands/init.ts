// ─────────────────────────────────────────────────────────────────────────────
// cli/commands/init.ts
// Initialises the QA platform for a new environment.
// Checks connectivity to backend, frontend, and Mailpit.
// Creates the artifacts directory and seeds an empty manifest.
// ─────────────────────────────────────────────────────────────────────────────

import fs from "node:fs";
import path from "node:path";
import { loadConfig, Logger } from "../../adapters/logger.js";
import { BackendAdapter } from "../../adapters/backend.js";
import { createEmptyManifest, loadManifest, manifestPath, saveManifest } from "../../core/manifest.js";
import { clearCache } from "../../core/cache.js";

const logger = new Logger("init");

interface InitOptions {
  skipChecks?: boolean;
}

export async function initCommand(options: InitOptions): Promise<void> {
  logger.info("Initialising QA platform...\n");

  const config = loadConfig();

  // ── Artifacts directory ───────────────────────────────────────────────────
  fs.mkdirSync(config.artifactsDir, { recursive: true });
  fs.mkdirSync(path.join(config.artifactsDir, "runs"), { recursive: true });
  logger.info(`✅ Artifacts directory: ${config.artifactsDir}`);

  // ── Clear step cache ──────────────────────────────────────────────────────
  clearCache();
  logger.info("✅ Step cache cleared");

  // ── Manifest init ─────────────────────────────────────────────────────────
  if (!fs.existsSync(manifestPath)) {
    saveManifest(createEmptyManifest());
    logger.info("✅ domain-manifest.json created");
  } else {
    const manifest = loadManifest();
    const count = Object.keys(manifest.domains).length;
    logger.info(`✅ domain-manifest.json exists (${count} domain${count !== 1 ? "s" : ""})`);
  }

  // ── Connectivity checks ───────────────────────────────────────────────────
  if (options.skipChecks) {
    logger.warn("Connectivity checks skipped (--skip-checks)");
    logger.info("\nInit complete.");
    return;
  }

  logger.info("\nChecking connectivity...\n");
  const failures: string[] = [];

  // Backend
  const backend = new BackendAdapter(config);
  const backendOk = await backend.isReachable();
  if (backendOk) {
    logger.info(`  ✅ Backend     ${config.apiBaseUrl}`);
  } else {
    logger.error(`  ✗  Backend     ${config.apiBaseUrl} — not reachable`);
    failures.push("backend");
  }

  // Frontend
  const frontendOk = await isUrlReachable(config.baseUrl);
  if (frontendOk) {
    logger.info(`  ✅ Frontend    ${config.baseUrl}`);
  } else {
    logger.warn(`  ⚠  Frontend    ${config.baseUrl} — not reachable (may be expected in API-only runs)`);
  }

  // Mailpit
  const mailpitOk = await isUrlReachable(`${config.mailpitUrl}/api/v1/messages`);
  if (mailpitOk) {
    logger.info(`  ✅ Mailpit     ${config.mailpitUrl}`);
  } else {
    logger.warn(`  ⚠  Mailpit     ${config.mailpitUrl} — not reachable (required for OTP flows)`);
  }

  if (failures.length > 0) {
    logger.error(`\nInit completed with failures: ${failures.join(", ")}`);
    logger.error("Ensure the required services are running before running QA.");
    process.exit(1);
  }

  logger.info("\nInit complete. Run: pnpm qa:run");
}

async function isUrlReachable(url: string): Promise<boolean> {
  try {
    const response = await fetch(url, { signal: AbortSignal.timeout(5000) });
    return response.status < 500;
  } catch {
    return false;
  }
}
