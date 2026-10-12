import assert from "node:assert/strict";
import test from "node:test";

import { consumeNdjson, ProgressiveEngineRegistry } from "../static/progressive-engine.mjs";

test("shallow snapshots are replaced by deeper snapshots for the active position", () => {
  const registry = new ProgressiveEngineRegistry();
  const request = registry.begin("analysis", { fen: "fen-a", targetDepth: 14, multipv: 2 });
  assert.equal(registry.accept("analysis", request.id, { fen: "fen-a", depth: 6 }), true);
  assert.equal(registry.accept("analysis", request.id, { fen: "fen-a", depth: 10 }), true);
  assert.equal(registry.peek("fen-a", 14, 2).depth, 10);
});

test("a stale position cannot overwrite the current position", () => {
  const registry = new ProgressiveEngineRegistry();
  const first = registry.begin("analysis", { fen: "fen-a", targetDepth: 14, multipv: 2 });
  const second = registry.begin("analysis", { fen: "fen-b", targetDepth: 14, multipv: 2 });
  assert.equal(first.signal.aborted, true);
  assert.equal(registry.accept("analysis", first.id, { fen: "fen-a", depth: 14 }), false);
  assert.equal(registry.accept("analysis", second.id, { fen: "fen-b", depth: 6 }), true);
});

test("revisiting a position exposes its strongest cached result immediately", () => {
  const registry = new ProgressiveEngineRegistry();
  const first = registry.begin("analysis", { fen: "fen-a", targetDepth: 14, multipv: 2 });
  registry.accept("analysis", first.id, { fen: "fen-a", depth: 6 });
  registry.accept("analysis", first.id, { fen: "fen-a", depth: 14 });
  const revisit = registry.begin("analysis", { fen: "fen-a", targetDepth: 10, multipv: 2 });
  assert.equal(revisit.cached.depth, 6);
});

test("explicit cancellation aborts the active stream", () => {
  const registry = new ProgressiveEngineRegistry();
  const request = registry.begin("analysis", { fen: "fen-a", targetDepth: 10, multipv: 2 });
  registry.cancel("analysis");
  assert.equal(request.signal.aborted, true);
  assert.equal(registry.isCurrent("analysis", request.id), false);
});

test("NDJSON values are emitted across arbitrary chunk boundaries", async () => {
  const encoder = new TextEncoder();
  const response = new Response(new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode('{"depth":6}\n{"dep'));
      controller.enqueue(encoder.encode('th":10}\n'));
      controller.close();
    },
  }));
  const values = [];
  await consumeNdjson(response, (value) => values.push(value));
  assert.deepEqual(values, [{ depth: 6 }, { depth: 10 }]);
});
