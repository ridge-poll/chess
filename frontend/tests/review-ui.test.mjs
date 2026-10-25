import assert from "node:assert/strict";
import test from "node:test";

import { adjacentCriticalPly, lastMoveSquares, QUALITY_SYMBOLS } from "../static/review-ui.mjs";

const moves = [
  { ply: 1, uci: "e2e4" },
  { ply: 2, uci: "c7c5" },
  { ply: 3, uci: "g1f3" },
];

test("last-move highlighting follows the selected ply and clears at start", () => {
  assert.equal(lastMoveSquares(moves, 0), null);
  assert.deepEqual(lastMoveSquares(moves, 3), { from: "g1", to: "f3" });
  assert.deepEqual(lastMoveSquares(moves, 2), { from: "c7", to: "c5" });
});

test("last-move squares remain board coordinates when orientation flips", () => {
  assert.deepEqual(lastMoveSquares(moves, 1), lastMoveSquares(moves, 1));
});

test("critical navigation wraps and lands after the selected move", () => {
  const moments = [{ ply: 4 }, { ply: 11 }, { ply: 18 }];
  assert.equal(adjacentCriticalPly(moments, 4, "next"), 11);
  assert.equal(adjacentCriticalPly(moments, 18, "next"), 4);
  assert.equal(adjacentCriticalPly(moments, 11, "prev"), 4);
  assert.equal(adjacentCriticalPly(moments, 4, "prev"), 18);
});

test("quality markers communicate meaning without color", () => {
  assert.equal(QUALITY_SYMBOLS.best, "★");
  assert.equal(QUALITY_SYMBOLS.good, "✓");
  assert.equal(QUALITY_SYMBOLS.inaccuracy, "?!");
  assert.equal(QUALITY_SYMBOLS.mistake, "?");
  assert.equal(QUALITY_SYMBOLS.blunder, "??");
});
