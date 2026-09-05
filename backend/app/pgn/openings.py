from __future__ import annotations

from urllib.parse import unquote

from app.models import ParsedMove


OPENING_PATTERNS: list[tuple[tuple[str, ...], str]] = [
    (("e4", "c5"), "Sicilian Defense"),
    (("e4", "e6"), "French Defense"),
    (("e4", "e5", "Nf3", "Nc6", "Bb5"), "Ruy Lopez"),
    (("e4", "e5", "Nf3", "Nc6", "Bc4"), "Italian Game"),
    (("e4", "e5"), "Open Game"),
    (("e4", "c6"), "Caro-Kann Defense"),
    (("e4", "d6"), "Pirc Defense"),
    (("e4", "g6"), "Modern Defense"),
    (("d4", "Nf6", "c4", "g6"), "King's Indian Defense"),
    (("d4", "Nf6", "c4", "e6", "Nc3", "Bb4"), "Nimzo-Indian Defense"),
    (("d4", "Nf6", "c4", "e6"), "Queen's Pawn Indian Game"),
    (("d4", "d5", "c4", "e6"), "Queen's Gambit Declined"),
    (("d4", "d5", "c4", "dxc4"), "Queen's Gambit Accepted"),
    (("d4", "d5", "c4", "c6"), "Slav Defense"),
    (("d4", "d5", "c4"), "Queen's Gambit"),
    (("d4", "d5"), "Queen's Pawn Game"),
    (("c4",), "English Opening"),
    (("Nf3",), "Reti Opening"),
    (("f4",), "Bird's Opening"),
]


def detect_opening(
    moves: list[ParsedMove],
    header_opening: str | None = None,
    eco_url: str | None = None,
) -> str | None:
    if header_opening:
        return header_opening

    url_opening = _opening_from_eco_url(eco_url)
    if url_opening:
        return url_opening

    sans = tuple(move.san.replace("+", "").replace("#", "") for move in moves[:8])
    best_match: tuple[str, ...] | None = None
    best_name: str | None = None
    for pattern, name in OPENING_PATTERNS:
        if len(sans) >= len(pattern) and sans[: len(pattern)] == pattern:
            if best_match is None or len(pattern) > len(best_match):
                best_match = pattern
                best_name = name
    return best_name


def _opening_from_eco_url(eco_url: str | None) -> str | None:
    if not eco_url:
        return None
    slug = unquote(eco_url.rstrip("/").split("/")[-1])
    if not slug:
        return None
    parts = []
    for token in slug.split("-"):
        if token.startswith(("1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.")):
            break
        parts.append(token)
    name = " ".join(parts).strip()
    return name or None
