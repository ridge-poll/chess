# Chess Analytics

Mobile-first chess analytics app for importing Chess.com PGNs, analyzing games with Stockfish, and tracking long-term performance.

## Stage 1 Scope

- Import one or more PGNs from Chess.com exports.
- Parse core metadata: date, result, color, ECO, opening, time control, ratings.
- Detect duplicate games by normalized metadata and move text.
- Store games, moves, analysis jobs, and engine results in SQLite.
- Analyze games with Stockfish through `python-chess`.
- Cache evaluations by position/depth and skip already analyzed games.
- Resume interrupted analysis from the first unanalyzed ply.
- Show a phone-friendly dashboard, trends, openings, phase stats, mistakes, and game detail.

## Stage 2 Additions

- Analysis runs through a local background queue instead of blocking the browser request.
- Queue state is stored in SQLite as `queued`, `running`, `complete`, or `failed`.
- Interrupted `queued`/`running` jobs are marked failed on backend startup and can be re-queued.
- Completed games are skipped before Stockfish is opened.
- Partially analyzed games resume from the first missing ply.
- The Games view includes a depth control and live queue progress.

## Stage 3 Additions

- Player-aware win/loss/draw and rating trend when a primary player can be inferred.
- Coach notes summarizing current baseline, recent form, phase focus, openings, and conversion issues.
- Opening summaries for frequency, score rate, best openings, and weakest openings.
- Phase labels that identify current strength and focus areas.
- Mistake breakdown for inaccuracies, mistakes, blunders, large eval swings, conversion misses, and defensive saves.

## Stage 4 Additions

- Chess.com public archive sync by username.
- Incremental month sync that skips previously completed archive months.
- Force re-sync option for refreshing already-synced months.
- Sync history stored in SQLite.
- Duplicate-safe imports reuse the PGN importer and fingerprinting.

Chess.com sync uses the public read-only PubAPI:

- Archive list: `https://api.chess.com/pub/player/{username}/games/archives`
- Monthly PGN: `https://api.chess.com/pub/player/{username}/games/{YYYY}/{MM}/pgn`

## Stage 5 Additions

- Installable PWA manifest.
- Service worker for cached app shell assets.
- Mobile safe-area styling and touch-friendly sync/settings controls.
- No JavaScript build step; FastAPI serves the mobile web app directly.

## Current UI Additions

- Profile-scoped game data, statistics, openings, and imports.
- Per-move/FEN analysis storage for game exploration.
- Interactive board explorer with move navigation and synced move selection.
- User-perspective evaluation graph with a simple Chess.com-style trace.
- Chess.com green board colors and minimal piece rendering.
- Persisted light/dark mode toggle.

## Tech Stack

- Backend: FastAPI, SQLite, python-chess
- Engine: Stockfish binary configured with `STOCKFISH_PATH`
- Frontend: mobile-first web app served by FastAPI, no build step required

This keeps the first version easy to run locally and leaves room for a later hosted backend, background workers, Chess.com sync, or PWA packaging.

## Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Install Stockfish separately, then set the path if it is not on `PATH`:

```bash
export STOCKFISH_PATH=/path/to/stockfish
```

Run the app:

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

Open [http://localhost:8000](http://localhost:8000).

## Tests

```bash
cd backend
source .venv/bin/activate
pytest
```

## Notes

- Without Stockfish installed, import and dashboard features still work; analysis endpoints return a clear error.
- SQLite data is stored at `backend/data/chess_analytics.sqlite3` by default.
- Override with `CHESS_ANALYTICS_DB=/path/to/file.sqlite3`.
- Chess piece SVGs in `frontend/static/pieces/cburnett/` are the Cburnett Staunton chess set from Wikimedia Commons, used under the available open-license terms including BSD/GFDL/GPL/CC BY-SA options.
