const FILES = "abcdefgh";

export function parseFenPieces(fen) {
  const rows = String(fen || "").split(" ")[0].split("/");
  if (rows.length !== 8) return {};
  const pieces = {};
  rows.forEach((row, rowIndex) => {
    let file = 0;
    for (const token of row) {
      const empty = Number(token);
      if (Number.isInteger(empty) && empty > 0) {
        file += empty;
      } else if (file < 8) {
        pieces[`${FILES[file]}${8 - rowIndex}`] = token;
        file += 1;
      }
    }
  });
  return pieces;
}

function pieceColor(piece) {
  return piece === piece.toUpperCase() ? "white" : "black";
}

function squareDistance(from, to) {
  return Math.abs(FILES.indexOf(from[0]) - FILES.indexOf(to[0]))
    + Math.abs(Number(from[1]) - Number(to[1]));
}

function isPromotion(from, to) {
  if (pieceColor(from.piece) !== pieceColor(to.piece)) return false;
  const forward = from.piece.toLowerCase() === "p" && ["1", "8"].includes(to.square[1]);
  const reverse = to.piece.toLowerCase() === "p" && ["1", "8"].includes(from.square[1]);
  return forward || reverse;
}

export function boardMotionDuration({ reduced = false, rapid = false } = {}) {
  if (reduced) return 0;
  return rapid ? 85 : 170;
}

export function pieceMotionGeometry(sourceSquare, destinationSquare, destinationPiece) {
  if (!sourceSquare || !destinationSquare || !destinationPiece) return null;
  const insetX = destinationPiece.left - destinationSquare.left;
  const insetY = destinationPiece.top - destinationSquare.top;
  const startLeft = sourceSquare.left + insetX;
  const startTop = sourceSquare.top + insetY;
  return {
    left: startLeft,
    top: startTop,
    width: destinationPiece.width,
    height: destinationPiece.height,
    translateX: destinationPiece.left - startLeft,
    translateY: destinationPiece.top - startTop,
  };
}

export function planBoardTransition(previousFen, nextFen) {
  const previous = parseFenPieces(previousFen);
  const next = parseFenPieces(nextFen);
  const removed = Object.entries(previous)
    .filter(([square, piece]) => next[square] !== piece)
    .map(([square, piece]) => ({ square, piece }));
  const added = Object.entries(next)
    .filter(([square, piece]) => previous[square] !== piece)
    .map(([square, piece]) => ({ square, piece }));
  const available = new Set(added.map((_, index) => index));
  const moves = [];

  for (const source of removed) {
    const candidates = [...available]
      .filter((index) => added[index].piece === source.piece || isPromotion(source, added[index]))
      .sort((left, right) => squareDistance(source.square, added[left].square) - squareDistance(source.square, added[right].square));
    if (!candidates.length) continue;
    const index = candidates[0];
    available.delete(index);
    moves.push({
      from: source.square,
      to: added[index].square,
      piece: source.piece,
      resultingPiece: added[index].piece,
      promotion: source.piece !== added[index].piece,
    });
  }

  const movedSources = new Set(moves.map((move) => move.from));
  return {
    moves,
    disappearing: removed.filter((piece) => !movedSources.has(piece.square)),
    appearing: [...available].map((index) => added[index]),
  };
}

export function createHoldNavigator(step, options = {}) {
  const delay = options.delay ?? 350;
  const interval = options.interval ?? 140;
  let stopped = false;
  let holding = false;
  let busy = false;
  let timer = null;

  const run = async () => {
    if (stopped || busy) return;
    busy = true;
    try {
      await step({ holding });
    } finally {
      busy = false;
    }
  };

  const repeat = async () => {
    if (stopped) return;
    holding = true;
    await run();
    if (!stopped) timer = setTimeout(repeat, interval);
  };

  void run();
  timer = setTimeout(repeat, delay);
  return {
    stop() {
      stopped = true;
      clearTimeout(timer);
    },
    get holding() {
      return holding && !stopped;
    },
  };
}
