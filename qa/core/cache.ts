// ─────────────────────────────────────────────────────────────────────────────
// core/cache.ts
// File-backed cache for idempotent bootstrap steps.
// Steps flagged idempotent: true are skipped when a fresh cache entry exists.
// Cache lives at qa/.qa-cache/steps.json — gitignored, local only.
// ─────────────────────────────────────────────────────────────────────────────

import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";

const CACHE_DIR = path.resolve(process.cwd(), ".qa-cache");
const CACHE_FILE = path.join(CACHE_DIR, "steps.json");

interface CacheEntry {
  hash: string;
  cachedAt: number; // Unix timestamp ms
}

type CacheStore = Record<string, CacheEntry>;

function loadStore(): CacheStore {
  try {
    if (!fs.existsSync(CACHE_FILE)) return {};
    const raw = fs.readFileSync(CACHE_FILE, "utf-8");
    return JSON.parse(raw) as CacheStore;
  } catch {
    return {};
  }
}

function saveStore(store: CacheStore): void {
  try {
    fs.mkdirSync(CACHE_DIR, { recursive: true });
    fs.writeFileSync(CACHE_FILE, JSON.stringify(store, null, 2), "utf-8");
  } catch {
    // Cache write failure is non-fatal — step will simply execute
  }
}

/**
 * Generates a deterministic cache key from a step label, action, and payload.
 * Two steps with identical label+action+payload produce the same key.
 */
export function buildCacheKey(
  domainName: string,
  stepLabel: string,
  action: string,
  payload?: Record<string, unknown>
): string {
  const raw = JSON.stringify({ domainName, stepLabel, action, payload: payload ?? {} });
  return crypto.createHash("sha256").update(raw).digest("hex").slice(0, 16);
}

/**
 * Returns true if a valid (non-expired) cache entry exists for the given key.
 * @param ttlSeconds — from QAConfig.cacheTtl
 */
export function isCached(key: string, ttlSeconds: number): boolean {
  const store = loadStore();
  const entry = store[key];
  if (!entry) return false;

  const ageMs = Date.now() - entry.cachedAt;
  const ttlMs = ttlSeconds * 1000;
  return ageMs < ttlMs;
}

/**
 * Writes a cache entry for the given key.
 * Call this after a step executes successfully.
 */
export function setCached(key: string, hash: string): void {
  const store = loadStore();
  store[key] = { hash, cachedAt: Date.now() };
  saveStore(store);
}

/**
 * Removes all cache entries. Called by `qa:init` to force fresh state.
 */
export function clearCache(): void {
  try {
    if (fs.existsSync(CACHE_FILE)) fs.unlinkSync(CACHE_FILE);
  } catch {
    // Non-fatal
  }
}

/**
 * Removes expired entries from the cache store.
 * Lightweight housekeeping — called at the start of each run.
 */
export function pruneExpiredCache(ttlSeconds: number): void {
  const store = loadStore();
  const ttlMs = ttlSeconds * 1000;
  let changed = false;

  for (const key of Object.keys(store)) {
    const entry = store[key];
    if (entry && Date.now() - entry.cachedAt >= ttlMs) {
      delete store[key];
      changed = true;
    }
  }

  if (changed) saveStore(store);
}
