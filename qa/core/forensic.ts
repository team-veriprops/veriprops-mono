// ─────────────────────────────────────────────────────────────────────────────
// core/forensic.ts
// Captures screenshots, DOM snapshots, JSON dumps, and logs on step failure.
// Manages artifact directories and prunes old runs to stay within MAX_RUNS.
// ─────────────────────────────────────────────────────────────────────────────

import fs from "node:fs";
import path from "node:path";
import type { Page } from "@playwright/test";
import type { ForensicArtifacts, ForensicSnapshot } from "./types.js";

// ─── Artifact Root ────────────────────────────────────────────────────────────

/**
 * Creates the artifact directory for a single run.
 * Structure: <artifactsDir>/runs/<runId>/<domainName>/<journeyName>/
 */
export function createArtifactRoot(
  artifactsDir: string,
  runId: string,
  domainName: string,
  journeyName: string
): string {
  const safe = (s: string) => s.replace(/[^a-z0-9-_]/gi, "_");
  const dir = path.resolve(
    artifactsDir,
    "runs",
    runId,
    safe(domainName),
    safe(journeyName)
  );
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

// ─── Retention Pruning ────────────────────────────────────────────────────────

/**
 * Prunes the oldest run directories under <artifactsDir>/runs/ so that
 * no more than `maxRuns` directories are retained.
 * Called by the orchestrator at the start of each run after creating the new dir.
 */
export function pruneOldRuns(artifactsDir: string, maxRuns: number): void {
  const runsDir = path.resolve(artifactsDir, "runs");
  if (!fs.existsSync(runsDir)) return;

  const entries = fs
    .readdirSync(runsDir, { withFileTypes: true })
    .filter((e) => e.isDirectory())
    .map((e) => ({
      name: e.name,
      fullPath: path.join(runsDir, e.name),
      mtimeMs: fs.statSync(path.join(runsDir, e.name)).mtimeMs,
    }))
    .sort((a, b) => a.mtimeMs - b.mtimeMs); // oldest first

  const excess = entries.length - maxRuns;
  if (excess <= 0) return;

  for (const entry of entries.slice(0, excess)) {
    try {
      fs.rmSync(entry.fullPath, { recursive: true, force: true });
      console.log(`[forensic] Pruned old run: ${entry.name}`);
    } catch (err) {
      console.warn(`[forensic] Failed to prune run "${entry.name}":`, err);
    }
  }
}

// ─── ForensicCapture ─────────────────────────────────────────────────────────

export class ForensicCapture {
  private artifacts: ForensicArtifacts;
  private artifactDir: string;

  constructor(
    runId: string,
    domainName: string,
    journeyName: string,
    artifactsDir: string
  ) {
    this.artifactDir = createArtifactRoot(artifactsDir, runId, domainName, journeyName);
    this.artifacts = { runId, domainName, journeyName, snapshots: [] };
  }

  // ─── Capture methods ────────────────────────────────────────────────────────

  async captureScreenshot(page: Page, label: string): Promise<ForensicSnapshot> {
    const timestamp = new Date().toISOString();
    const filename = `screenshot-${sanitize(label)}-${Date.now()}.png`;
    const screenshotPath = path.join(this.artifactDir, filename);

    try {
      await page.screenshot({ path: screenshotPath, fullPage: true });
    } catch (err) {
      console.warn(`[forensic] Screenshot failed for "${label}":`, err);
    }

    const snapshot: ForensicSnapshot = { timestamp, screenshotPath };
    this.artifacts.snapshots.push(snapshot);
    return snapshot;
  }

  async captureDOMSnapshot(page: Page, label: string): Promise<ForensicSnapshot> {
    const timestamp = new Date().toISOString();
    const filename = `dom-${sanitize(label)}-${Date.now()}.html`;
    const domPath = path.join(this.artifactDir, filename);

    try {
      const html = await page.content();
      fs.writeFileSync(domPath, html, "utf-8");
    } catch (err) {
      console.warn(`[forensic] DOM snapshot failed for "${label}":`, err);
    }

    const snapshot: ForensicSnapshot = { timestamp, domPath };
    this.artifacts.snapshots.push(snapshot);
    return snapshot;
  }

  captureJSON(label: string, data: unknown): ForensicSnapshot {
    const timestamp = new Date().toISOString();
    const filename = `data-${sanitize(label)}-${Date.now()}.json`;
    const jsonPath = path.join(this.artifactDir, filename);

    try {
      fs.writeFileSync(jsonPath, JSON.stringify(data, null, 2), "utf-8");
    } catch (err) {
      console.warn(`[forensic] JSON capture failed for "${label}":`, err);
    }

    const snapshot: ForensicSnapshot = { timestamp, jsonPath };
    this.artifacts.snapshots.push(snapshot);
    return snapshot;
  }

  writeLog(lines: string[]): ForensicSnapshot {
    const timestamp = new Date().toISOString();
    const logPath = path.join(this.artifactDir, "run.log");

    try {
      const content = lines.map((l) => `[${timestamp}] ${l}`).join("\n") + "\n";
      fs.appendFileSync(logPath, content, "utf-8");
    } catch (err) {
      console.warn(`[forensic] Log write failed:`, err);
    }

    const snapshot: ForensicSnapshot = { timestamp, logPath };
    this.artifacts.snapshots.push(snapshot);
    return snapshot;
  }

  writeReport(data: unknown): void {
    const reportPath = path.join(this.artifactDir, "report.json");
    try {
      fs.writeFileSync(reportPath, JSON.stringify(data, null, 2), "utf-8");
    } catch (err) {
      console.warn(`[forensic] Report write failed:`, err);
    }
  }

  writeManifestSnapshot(manifest: unknown): void {
    const snapshotPath = path.join(this.artifactDir, "manifest-snapshot.json");
    try {
      fs.writeFileSync(snapshotPath, JSON.stringify(manifest, null, 2), "utf-8");
    } catch (err) {
      console.warn(`[forensic] Manifest snapshot failed:`, err);
    }
  }

  getArtifacts(): ForensicArtifacts {
    return this.artifacts;
  }

  getArtifactDir(): string {
    return this.artifactDir;
  }
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function sanitize(label: string): string {
  return label.replace(/[^a-z0-9-]/gi, "_").toLowerCase().slice(0, 40);
}
