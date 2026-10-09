// Run with `node --test` from infra/cloudflare/sweep-cron (Node 20+, no dependencies).
import assert from "node:assert/strict";
import { test } from "node:test";

import { runTick, tickHeaders } from "../src/index.js";

const ENV = {
  TICK_URL: "https://api-dev.veriprops.ng/api/internal/sweeps/tick",
  SWEEP_TRIGGER_SECRET: "sweep-secret",
};

function answering(status, data) {
  const calls = [];
  const fetchImpl = async (url, init) => {
    calls.push({ url, init });
    return new Response(JSON.stringify(data), { status });
  };
  return { calls, fetchImpl };
}

test("posts to the tick URL with the sweep secret", async () => {
  const { calls, fetchImpl } = answering(200, { data: { jobs: [] } });

  await runTick(ENV, fetchImpl);

  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, ENV.TICK_URL);
  assert.equal(calls[0].init.method, "POST");
  assert.deepEqual(calls[0].init.headers, { "x-sweep-secret": "sweep-secret" });
});

test("adds the edge-auth header only when the environment enforces it", () => {
  assert.deepEqual(tickHeaders({ ...ENV, EDGE_AUTH_SECRET: "edge" }), {
    "x-sweep-secret": "sweep-secret",
    "x-edge-auth": "edge",
  });
  assert.equal("x-edge-auth" in tickHeaders(ENV), false);
});

test("honours custom header names", () => {
  const headers = tickHeaders({
    ...ENV, EDGE_AUTH_SECRET: "edge", SWEEP_TRIGGER_HEADER: "x-s", EDGE_AUTH_HEADER: "x-e",
  });
  assert.deepEqual(headers, { "x-s": "sweep-secret", "x-e": "edge" });
});

test("refuses to run unconfigured", async () => {
  await assert.rejects(runTick({ ...ENV, SWEEP_TRIGGER_SECRET: "" }, answering(200, {}).fetchImpl), /SWEEP_TRIGGER_SECRET/);
  await assert.rejects(runTick({ ...ENV, TICK_URL: "" }, answering(200, {}).fetchImpl), /TICK_URL/);
});

test("a refused tick fails the invocation", async () => {
  await assert.rejects(runTick(ENV, answering(404, {}).fetchImpl), /HTTP 404/);
  await assert.rejects(runTick(ENV, answering(401, {}).fetchImpl), /HTTP 401/);
});

test("a failed sweep fails the invocation, after the tick ran the rest", async () => {
  const jobs = [{ name: "a", outcome: "FAILED" }, { name: "b", outcome: "RAN" }];
  await assert.rejects(runTick(ENV, answering(200, { data: { jobs } }).fetchImpl), /a sweep failed/);
});

test("returns the tick's job summary", async () => {
  const jobs = [{ name: "message_retry_check", outcome: "RAN", durationMs: 4 }];
  assert.deepEqual(await runTick(ENV, answering(200, { data: { jobs } }).fetchImpl), jobs);
});
