function clampPly(ply, maximum) {
  return Math.max(0, Math.min(Number(ply) || 0, maximum));
}

function copySession(session, changes = {}) {
  return {
    mainLineMoves: [...session.mainLineMoves],
    currentPly: session.currentPly,
    branchPoint: session.branchPoint,
    variationMoves: [...session.variationMoves],
    orientation: session.orientation,
    ...changes,
  };
}

export function createAnalysisSession(mainLineMoves, selectedPly = 0, orientation = "white") {
  const moves = [...(mainLineMoves || [])];
  return {
    mainLineMoves: moves,
    currentPly: clampPly(selectedPly, moves.length),
    branchPoint: null,
    variationMoves: [],
    orientation: orientation === "black" ? "black" : "white",
  };
}

export function hasActiveVariation(session) {
  return session.branchPoint != null && session.currentPly > session.branchPoint;
}

export function analysisPathMoves(session) {
  if (session.branchPoint == null) return [...session.mainLineMoves];
  return [
    ...session.mainLineMoves.slice(0, session.branchPoint),
    ...session.variationMoves,
  ];
}

export function analysisPositionMoves(session) {
  return analysisPathMoves(session).slice(0, session.currentPly);
}

export function playAnalysisMove(session, move) {
  const uci = String(move || "");
  if (!uci) return copySession(session);

  if (session.branchPoint == null) {
    const mainLineNext = session.mainLineMoves[session.currentPly];
    if (mainLineNext === uci) {
      return copySession(session, { currentPly: session.currentPly + 1 });
    }
    return copySession(session, {
      currentPly: session.currentPly + 1,
      branchPoint: session.currentPly,
      variationMoves: [uci],
    });
  }

  const variationIndex = session.currentPly - session.branchPoint;
  const existingNext = session.variationMoves[variationIndex];
  if (existingNext === uci) {
    return copySession(session, { currentPly: session.currentPly + 1 });
  }
  return copySession(session, {
    currentPly: session.currentPly + 1,
    variationMoves: [...session.variationMoves.slice(0, variationIndex), uci],
  });
}

export function stepAnalysisBackward(session) {
  if (session.currentPly <= 0) return copySession(session);
  const nextPly = session.currentPly - 1;
  if (session.branchPoint != null && nextPly <= session.branchPoint) {
    return copySession(session, {
      currentPly: session.branchPoint,
      branchPoint: null,
      variationMoves: [],
    });
  }
  return copySession(session, { currentPly: nextPly });
}

export function stepAnalysisForward(session) {
  const path = analysisPathMoves(session);
  return copySession(session, { currentPly: Math.min(path.length, session.currentPly + 1) });
}

export function selectAnalysisMainLinePly(session, ply) {
  return copySession(session, {
    currentPly: clampPly(ply, session.mainLineMoves.length),
    branchPoint: null,
    variationMoves: [],
  });
}

export function selectAnalysisVariationPly(session, ply) {
  if (session.branchPoint == null) return selectAnalysisMainLinePly(session, ply);
  const selected = clampPly(ply, session.branchPoint + session.variationMoves.length);
  if (selected <= session.branchPoint) {
    return selectAnalysisMainLinePly(session, session.branchPoint);
  }
  return copySession(session, { currentPly: selected });
}

export function flipAnalysisOrientation(session) {
  return copySession(session, {
    orientation: session.orientation === "white" ? "black" : "white",
  });
}
