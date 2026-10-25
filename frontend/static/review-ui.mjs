export const QUALITY_SYMBOLS = Object.freeze({
  best: "★",
  great: "★",
  good: "✓",
  inaccuracy: "?!",
  mistake: "?",
  blunder: "??",
});

export function lastMoveSquares(moves, selectedPly) {
  const ply = Number(selectedPly) || 0;
  if (ply <= 0) return null;
  const move = moves.find((item) => Number(item.ply) === ply);
  const uci = String(move?.uci || "");
  return uci.length >= 4 ? { from: uci.slice(0, 2), to: uci.slice(2, 4) } : null;
}

export function adjacentCriticalPly(moments, currentPly, direction) {
  const plies = moments.map((moment) => Number(moment.ply)).filter(Number.isFinite).sort((a, b) => a - b);
  if (!plies.length) return null;
  const current = Number(currentPly) || 0;
  if (direction === "prev") return [...plies].reverse().find((ply) => ply < current) ?? plies.at(-1);
  return plies.find((ply) => ply > current) ?? plies[0];
}

export function resolveActiveProfile(profiles, activeProfile, storedId) {
  if (!Array.isArray(profiles)) return null;
  const stored = profiles.find((profile) => String(profile.id) === String(storedId));
  const active = profiles.find((profile) => String(profile.id) === String(activeProfile?.id));
  return stored || active || profiles[0] || null;
}
