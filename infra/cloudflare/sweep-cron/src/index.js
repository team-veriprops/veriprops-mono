/**
 * Veriprops sweep-cron Worker — the clock for the backend's scheduled jobs.
 *
 * Every deployed environment is serverless, where an in-process scheduler cannot be trusted to
 * fire. Cloudflare runs this Worker every minute (wrangler.toml `crons`), and it asks the
 * backend to run one sweep tick: `POST <TICK_URL>` with the sweep secret. The backend decides
 * which jobs are due and runs them; this Worker keeps no schedule of its own.
 *
 * Bindings (per environment):
 * - `TICK_URL` (var): the backend's tick endpoint on its own API host.
 * - `SWEEP_TRIGGER_SECRET` (secret): the backend's `SWEEP_TRIGGER_SECRET`.
 * - `EDGE_AUTH_SECRET` (secret, optional): the backend's `EDGE_AUTH_SECRET`. A Worker's
 *   subrequest may not pass through the zone's Transform Rule that normally adds the edge-auth
 *   header, so the Worker sends it itself whenever the environment enforces edge auth.
 * - `SWEEP_TRIGGER_HEADER` / `EDGE_AUTH_HEADER` (vars, optional): header names, when they
 *   differ from the backend's defaults.
 */

const DEFAULT_SWEEP_TRIGGER_HEADER = "x-sweep-secret";
const DEFAULT_EDGE_AUTH_HEADER = "x-edge-auth";

/** Outcomes worth a log line; the rest (NOT_DUE, CLAIMED_ELSEWHERE) are the quiet majority. */
const REPORTED_OUTCOMES = new Set(["RAN", "FAILED", "DEFERRED"]);

/** The headers that authorise one tick. */
export function tickHeaders(env) {
  if (!env.SWEEP_TRIGGER_SECRET) {
    throw new Error("SWEEP_TRIGGER_SECRET is not bound; run `wrangler secret put SWEEP_TRIGGER_SECRET --env <env>`");
  }
  const headers = { [env.SWEEP_TRIGGER_HEADER || DEFAULT_SWEEP_TRIGGER_HEADER]: env.SWEEP_TRIGGER_SECRET };
  if (env.EDGE_AUTH_SECRET) {
    headers[env.EDGE_AUTH_HEADER || DEFAULT_EDGE_AUTH_HEADER] = env.EDGE_AUTH_SECRET;
  }
  return headers;
}

/**
 * Ask the backend for one tick and log what it did. Throws on any non-2xx answer, so the
 * invocation shows as failed in Cloudflare's cron history; the backend's error body carries
 * only a safe sentence and a reference to look up in its logs.
 */
export async function runTick(env, fetchImpl = fetch) {
  if (!env.TICK_URL) {
    throw new Error("TICK_URL is not set; deploy with `wrangler deploy --env <dev|staging|production>`");
  }
  const response = await fetchImpl(env.TICK_URL, { method: "POST", headers: tickHeaders(env) });
  const body = await response.text();
  if (!response.ok) {
    throw new Error(`sweep tick answered HTTP ${response.status}: ${body.slice(0, 300)}`);
  }
  const jobs = JSON.parse(body)?.data?.jobs ?? [];
  const reported = jobs.filter((job) => REPORTED_OUTCOMES.has(job.outcome));
  if (reported.length) {
    console.log(`sweep tick: ${reported.map((job) => `${job.name}=${job.outcome}`).join(", ")}`);
  }
  if (jobs.some((job) => job.outcome === "FAILED")) {
    throw new Error("a sweep failed; see the backend logs");
  }
  return jobs;
}

export default {
  async scheduled(_controller, env, ctx) {
    ctx.waitUntil(runTick(env));
  },
};
