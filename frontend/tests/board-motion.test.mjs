import assert from "node:assert/strict";
import test from "node:test";

import { boardMotionDuration, createHoldNavigator, pieceMotionGeometry, planBoardTransition } from "../static/board-motion.mjs";

const START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

test("plans normal and reverse piece movement", () => {
  const after = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1";
  assert.deepEqual(planBoardTransition(START, after).moves, [
    { from: "e2", to: "e4", piece: "P", resultingPiece: "P", promotion: false },
  ]);
  assert.equal(planBoardTransition(after, START).moves[0].from, "e4");
  assert.equal(planBoardTransition(after, START).moves[0].to, "e2");
});

test("plans capture removal and reverse capture restoration", () => {
  const before = "8/8/8/3p4/4P3/8/8/8 w - - 0 1";
  const after = "8/8/8/3P4/8/8/8/8 b - - 0 1";
  const forward = planBoardTransition(before, after);
  assert.deepEqual(forward.moves[0], { from: "e4", to: "d5", piece: "P", resultingPiece: "P", promotion: false });
  assert.deepEqual(forward.disappearing, [{ square: "d5", piece: "p" }]);
  assert.deepEqual(planBoardTransition(after, before).appearing, [{ square: "d5", piece: "p" }]);
});

test("plans both castling pieces", () => {
  const before = "4k3/8/8/8/8/8/8/4K2R w K - 0 1";
  const after = "4k3/8/8/8/8/8/8/5RK1 b - - 1 1";
  assert.deepEqual(planBoardTransition(before, after).moves.map(({ from, to }) => ({ from, to })), [
    { from: "e1", to: "g1" },
    { from: "h1", to: "f1" },
  ]);
});

test("plans promotion as pawn movement with a resulting piece", () => {
  const before = "8/P7/8/8/8/8/8/4k2K w - - 0 1";
  const after = "Q7/8/8/8/8/8/8/4k2K b - - 0 1";
  assert.deepEqual(planBoardTransition(before, after).moves[0], {
    from: "a7", to: "a8", piece: "P", resultingPiece: "Q", promotion: true,
  });
  assert.deepEqual(planBoardTransition(after, before).moves[0], {
    from: "a8", to: "a7", piece: "Q", resultingPiece: "P", promotion: true,
  });
});

test("board flips do not create movement and reduced motion disables duration", () => {
  assert.deepEqual(planBoardTransition(START, START).moves, []);
  assert.equal(boardMotionDuration({ reduced: true }), 0);
  assert.equal(boardMotionDuration({ rapid: true }), 85);
  assert.equal(boardMotionDuration(), 170);
});

test("animation endpoint exactly matches the static destination piece", () => {
  const source = { left: 0.25, top: 312.625, width: 48.75, height: 48.75 };
  const destinationSquare = { left: 195.25, top: 215.125, width: 48.75, height: 48.75 };
  const destinationPiece = { left: 199.625, top: 219.5, width: 39.975, height: 39.975 };
  const geometry = pieceMotionGeometry(source, destinationSquare, destinationPiece);

  assert.ok(geometry);
  assert.equal(geometry.left + geometry.translateX, destinationPiece.left);
  assert.equal(geometry.top + geometry.translateY, destinationPiece.top);
  assert.equal(geometry.width, destinationPiece.width);
  assert.equal(geometry.height, destinationPiece.height);
});

test("hold navigation steps immediately, repeats, and stops on release", async () => {
  let steps = 0;
  const navigator = createHoldNavigator(async () => { steps += 1; }, { delay: 15, interval: 10 });
  assert.equal(steps, 1);
  await new Promise((resolve) => setTimeout(resolve, 42));
  navigator.stop();
  const stoppedAt = steps;
  assert.ok(stoppedAt >= 3);
  await new Promise((resolve) => setTimeout(resolve, 25));
  assert.equal(steps, stoppedAt);
});

test("hold navigation serializes slow asynchronous steps", async () => {
  let active = 0;
  let maximumActive = 0;
  const navigator = createHoldNavigator(async () => {
    active += 1;
    maximumActive = Math.max(maximumActive, active);
    await new Promise((resolve) => setTimeout(resolve, 20));
    active -= 1;
  }, { delay: 5, interval: 5 });
  await new Promise((resolve) => setTimeout(resolve, 58));
  navigator.stop();
  assert.equal(maximumActive, 1);
});
