# Chess Analytics

A mobile-first chess improvement app for importing Chess.com games, analyzing them with Stockfish, and tracking long-term performance across profiles, openings, time controls, and game phases.

The repository now has two deliberately different execution environments:

- `backend/` + `frontend/`: the FastAPI/Python web laboratory for rapid experimentation.
- `mobile/`: the standalone Flutter production client, designed to store data and eventually run Stockfish directly on the device without requiring the web backend or a laptop.

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
- Explore master-game continuations through the authenticated Lichess Opening Explorer API.
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

Mobile foundation:

- Flutter and Dart
- Device-local SQLite via `sqflite`
- Device-local preferences via `shared_preferences`
- Repository/service boundaries for future direct Chess.com sync and local Stockfish

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

## Flutter Mobile App

The Flutter app is intentionally not a FastAPI client. Its current first checkpoint supports local profiles, persistent settings, and profile-scoped games stored in an on-device SQLite database.

```bash
cd mobile
flutter pub get
flutter run
```

Run mobile tests and build the unsigned iOS app:

```bash
cd mobile
flutter test
flutter build ios --simulator
```

The sample-game action on an empty Games screen exists only to demonstrate local persistence before direct Chess.com sync is added.

## Configuration

Environment variables:

- `STOCKFISH_PATH`: path to the Stockfish binary. Defaults to `stockfish`.
- `STOCKFISH_DEPTH`: default analysis depth. Defaults to `10`.
- `CHESS_ANALYTICS_DB`: SQLite database path. Defaults to `backend/data/chess_analytics.sqlite3`.
- `LICHESS_API_TOKEN`: Lichess OAuth or personal API token used for master opening data.
- `LICHESS_EXPLORER_URL`: optional Opening Explorer endpoint override.
- `OPENING_EXPLORER_CACHE_SECONDS`: successful master-position cache lifetime. Defaults to six hours.

Example:

```bash
export STOCKFISH_PATH=/opt/homebrew/bin/stockfish
export STOCKFISH_DEPTH=12
export CHESS_ANALYTICS_DB="$PWD/data/chess_analytics.sqlite3"
export LICHESS_API_TOKEN="your-token"
uvicorn app.main:app --reload --port 8000
```

Lichess currently requires authentication for its Opening Explorer endpoints. Without
`LICHESS_API_TOKEN`, the board remains fully functional and displays legal continuations
without master-game counts until credentials are configured.

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

- Flutter checkpoint 2: direct Chess.com sync into local SQLite.
- Flutter checkpoint 3: local Stockfish with progressive analysis, cancellation, and caching.
- Flutter checkpoint 4: local full-game analytics and shared Python/Dart reference fixtures.
- Flutter checkpoint 5: native board-first Analysis and post-game review.

## Credits

- Chess engine integration uses Stockfish.
- Chess rules and PGN/FEN handling use `python-chess`.
- Piece SVGs in `frontend/static/pieces/cburnett/` are the Cburnett Staunton chess set from Wikimedia Commons, available under the listed open-license terms.
