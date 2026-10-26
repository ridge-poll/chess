# Chess Analytics Mobile

The standalone, local-first Flutter client for Chess Analytics. It does not
require FastAPI or a laptop to launch, synchronize games, or read local data.

## Current Capabilities

- local profiles and preferences
- direct, forced Chess.com synchronization
- multi-game PGN parsing with legal move and FEN reconstruction
- duplicate-safe, profile-owned SQLite storage
- offline Games history after synchronization

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

Local Stockfish and full-game analytics arrive in the following migration
checkpoints. The web application remains the reference implementation while
those systems are ported to Dart.
