import io
from urllib.error import HTTPError

import pytest

import app.services.master_openings as master_openings


START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


class FakeResponse:
    def __init__(self, payload: str) -> None:
        self.buffer = io.BytesIO(payload.encode("utf-8"))

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def read(self) -> bytes:
        return self.buffer.read()


def test_master_explorer_normalizes_and_sorts_moves(monkeypatch) -> None:
    master_openings.clear_master_opening_cache()
    payload = """{
      "white": 12, "draws": 5, "black": 8,
      "opening": {"eco": "A00", "name": "Starting Position"},
      "moves": [
        {"uci": "g1f3", "san": "Nf3", "white": 2, "draws": 1, "black": 1},
        {"uci": "e2e4", "san": "e4", "white": 7, "draws": 3, "black": 5}
      ]
    }"""
    monkeypatch.setattr(master_openings, "urlopen", lambda *_args, **_kwargs: FakeResponse(payload))

    result = master_openings.master_opening_position(START_FEN)

    assert result["status"] == "ready"
    assert result["cached"] is False
    assert [move["san"] for move in result["moves"]] == ["e4", "Nf3"]
    assert result["moves"][0]["games"] == 15


def test_master_explorer_caches_position_responses(monkeypatch) -> None:
    master_openings.clear_master_opening_cache()
    calls = 0

    def fetch(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        return FakeResponse('{"white": 1, "draws": 0, "black": 0, "moves": []}')

    monkeypatch.setattr(master_openings, "urlopen", fetch)
    first = master_openings.master_opening_position(START_FEN)
    second = master_openings.master_opening_position(START_FEN)

    assert calls == 1
    assert first["cached"] is False
    assert second["cached"] is True


def test_master_explorer_reports_authentication_requirement(monkeypatch) -> None:
    master_openings.clear_master_opening_cache()

    def unauthorized(request, **_kwargs):
        raise HTTPError(request.full_url, 401, "Unauthorized", {}, None)

    monkeypatch.setattr(master_openings, "urlopen", unauthorized)
    with pytest.raises(master_openings.MasterExplorerUnavailable, match="Lichess access"):
        master_openings.master_opening_position(START_FEN)


def test_master_explorer_rejects_invalid_fen() -> None:
    with pytest.raises(ValueError, match="Invalid FEN"):
        master_openings.master_opening_position("not-a-fen")
