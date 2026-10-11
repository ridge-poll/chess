import assert from "node:assert/strict";
import test from "node:test";

import {
  analysisPathMoves,
  createAnalysisSession,
  flipAnalysisOrientation,
  hasActiveVariation,
  playAnalysisMove,
  stepAnalysisBackward,
  stepAnalysisForward,
} from "../static/analysis-session.mjs";

const MAIN_LINE = ["e2e4", "c7c5", "g1f3", "b8c6", "b1c3"];

test("saved main line steps backward and forward without changing", () => {
  let session = createAnalysisSession(MAIN_LINE, MAIN_LINE.length);
  session = stepAnalysisBackward(session);
  session = stepAnalysisBackward(session);
  assert.equal(session.currentPly, 3);
  session = stepAnalysisForward(session);
  assert.equal(session.currentPly, 4);
  assert.deepEqual(session.mainLineMoves, MAIN_LINE);
  assert.deepEqual(analysisPathMoves(session), MAIN_LINE);
});

test("a different move creates a temporary variation and preserves the main line", () => {
  const original = createAnalysisSession(MAIN_LINE, 3);
  const varied = playAnalysisMove(original, "e7e6");

  assert.equal(varied.branchPoint, 3);
  assert.equal(varied.currentPly, 4);
  assert.deepEqual(varied.variationMoves, ["e7e6"]);
  assert.deepEqual(varied.mainLineMoves, MAIN_LINE);
  assert.deepEqual(original.mainLineMoves, MAIN_LINE);
});

test("continuing and navigating within a variation follows the variation", () => {
  let session = createAnalysisSession(MAIN_LINE, 3);
  session = playAnalysisMove(session, "e7e6");
  session = playAnalysisMove(session, "b1c3");
  session = playAnalysisMove(session, "b8c6");
  assert.deepEqual(analysisPathMoves(session), ["e2e4", "c7c5", "g1f3", "e7e6", "b1c3", "b8c6"]);

  session = stepAnalysisBackward(session);
  assert.equal(session.currentPly, 5);
  session = stepAnalysisForward(session);
  assert.equal(session.currentPly, 6);
  assert.equal(hasActiveVariation(session), true);
});

test("backing onto the branch point discards the active variation", () => {
  let session = createAnalysisSession(MAIN_LINE, 3);
  session = playAnalysisMove(session, "e7e6");
  session = playAnalysisMove(session, "b1c3");
  session = stepAnalysisBackward(session);
  session = stepAnalysisBackward(session);

  assert.equal(session.currentPly, 3);
  assert.equal(hasActiveVariation(session), false);
  assert.equal(session.branchPoint, null);
  assert.deepEqual(session.variationMoves, []);
});

test("forward from a cleared branch point resumes the saved main line", () => {
  let session = createAnalysisSession(MAIN_LINE, 3);
  session = playAnalysisMove(session, "e7e6");
  session = stepAnalysisBackward(session);
  session = stepAnalysisForward(session);

  assert.equal(session.currentPly, 4);
  assert.equal(analysisPathMoves(session)[3], "b8c6");
});

test("flipping the board does not alter variation navigation", () => {
  let session = createAnalysisSession(MAIN_LINE, 3);
  session = playAnalysisMove(session, "e7e6");
  const path = analysisPathMoves(session);
  session = flipAnalysisOrientation(session);

  assert.equal(session.orientation, "black");
  assert.deepEqual(analysisPathMoves(session), path);
  assert.equal(session.currentPly, 4);
});

test("a reloaded saved session contains only the immutable game line", () => {
  let session = createAnalysisSession(MAIN_LINE, 3);
  session = playAnalysisMove(session, "e7e6");
  const reloaded = createAnalysisSession(MAIN_LINE, 3);

  assert.equal(reloaded.branchPoint, null);
  assert.deepEqual(reloaded.mainLineMoves, MAIN_LINE);
  assert.deepEqual(reloaded.variationMoves, []);
});
