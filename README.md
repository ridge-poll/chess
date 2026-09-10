# Chess Analytics

A mobile-first chess improvement app for importing Chess.com games, analyzing them with Stockfish, and tracking long-term performance across profiles, openings, time controls, and game phases.

The app is intentionally local-first: FastAPI serves the backend and frontend, SQLite stores the data, and Stockfish runs on your machine.

## Features

- Import one or many PGNs from Chess.com exports.
- Sync recent games from Chess.com's public API by username.
- Store a default Chess.com username and sync window per local profile.
- Maintain multiple independent local player profiles.
- Detect duplicate games per profile.
- Parse metadata including date, result, players, ratings, ECO, opening, time control, and time-control class.
- Analyze games with Stockfish through `python-chess`.
- Cache engine evaluations and Multi-PV candidates by FEN/depth.
- Resume interrupted game analysis and skip already analyzed plies.
- Store per-move FEN, clock data when available, engine evaluations, CPL, and move classification.
- Review saved games with a board, move list, quality summary, and user-perspective evaluation graph.
- Open any saved game position in a temporary analysis board without mutating the stored game.
- Use a standalone Analysis Board and Opening Explorer with legal move input.
- View top engine candidates in board workspaces.
- Browse opening statistics, time-control statistics, trends, and game history.
- Use the app comfortably on a phone with bottom navigation, dark mode, and PWA app-shell caching.

## Tech Stack

- Backend: FastAPI
- Chess logic: `python-chess`
- Engine: Stockfish
- Storage: SQLite
- Frontend: mobile-first HTML/CSS/JavaScript served directly by FastAPI
- Tests: pytest

There is no frontend build step.

## Requirements

- Python 3.10 or newer recommended
- Stockfish installed locally
- A modern browser

## Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Install Stockfish separately. If the `stockfish` binary is not already on your `PATH`, set `STOCKFISH_PATH`:

```bash
export STOCKFISH_PATH=/path/to/stockfish
```

Run the app:

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

Open `http://localhost:8000`.

## Configuration

Environment variables:

- `STOCKFISH_PATH`: path to the Stockfish binary. Defaults to `stockfish`.
- `STOCKFISH_DEPTH`: default analysis depth. Defaults to `10`.
- `CHESS_ANALYTICS_DB`: SQLite database path. Defaults to `backend/data/chess_analytics.sqlite3`.

Example:

```bash
export STOCKFISH_PATH=/opt/homebrew/bin/stockfish
export STOCKFISH_DEPTH=12
export CHESS_ANALYTICS_DB="$PWD/data/chess_analytics.sqlite3"
uvicorn app.main:app --reload --port 8000
```

## Testing

```bash
cd backend
source .venv/bin/activate
pytest
```

If macOS bytecode cache permissions get in the way, direct Python bytecode to a writable temp folder:

```bash
PYTHONPYCACHEPREFIX=/private/tmp/chess_pycache pytest
```

## Architecture

The app uses a single SQLite database with explicit profile ownership:

```text
Profile
  -> Games
      -> Moves
      -> Move Analyses

Position Evaluations
  -> Multi-PV Candidate Lines
```

Game data is profile-scoped. Switching profiles changes the games, dashboard, opening stats, time-control stats, imports, and sync preferences shown in the app.

Engine analysis is cached by position and depth. Saved-game analysis stores move-level results, while position-level candidate lines are retained separately so future metrics can be derived without rerunning full game analysis unnecessarily.

## Current Roadmap

- Engine candidates inside Analysis and Opening Explorer.
- Synchronized saved-game analysis view with board, graph, move list, and candidate context.
- Opening repertoire tree based on the user's own games.
- Human-centric metrics such as decision difficulty, volatility, resourcefulness, conversion efficiency, defensive resilience, and time allocation.

## Credits

- Chess engine integration uses Stockfish.
- Chess rules and PGN/FEN handling use `python-chess`.
- Piece SVGs in `frontend/static/pieces/cburnett/` are the Cburnett Staunton chess set from Wikimedia Commons, available under the listed open-license terms.
