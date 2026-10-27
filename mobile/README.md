# Chess Analytics Mobile

The standalone, local-first Flutter client for Chess Analytics. It does not
require FastAPI or a laptop to launch, synchronize games, or read local data.

## Current Capabilities

- local profiles and preferences
- direct, forced Chess.com synchronization
- multi-game PGN parsing with legal move and FEN reconstruction
- duplicate-safe, profile-owned SQLite storage
- offline Games history after synchronization
- embedded local Stockfish with progressive Multi-PV analysis
- cancellable searches and persistent position caching
- resumable full-game analysis with user accuracy and move classifications
- positive and negative Critical Moments
- versioned, confidence-aware estimated performance
- board-first saved-game Analysis with legal temporary variations
- player-oriented board, engine lines, evaluation bar, and Critical navigation

## Run

```bash
flutter pub get
flutter run
```

Run validation with:

```bash
flutter analyze
flutter test
```

Stockfish is provided by Lichess's GPL-3.0 `multistockfish` package. The web
application remains the reference implementation for analytics as native
diagnostic and board interfaces are added.
