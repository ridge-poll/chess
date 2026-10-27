import 'package:chess_analytics_mobile/data/local/app_database.dart';
import 'package:chess_analytics_mobile/data/repositories/sqlite_game_repository.dart';
import 'package:chess_analytics_mobile/data/repositories/sqlite_profile_repository.dart';
import 'package:chess_analytics_mobile/domain/analysis_session.dart';
import 'package:chess_analytics_mobile/services/chess_engine.dart';
import 'package:chess_analytics_mobile/app/widgets/chess_board.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

const sessionPgn = '''
[Event "Session"]
[Site "session-1"]
[Date "2026.10.27"]
[White "Player"]
[Black "Opponent"]
[Result "1-0"]
[TimeControl "600"]

1. e4 c5 2. Nf3 Nc6 3. Nc3 1-0
''';

class QuietEngine implements ChessEngine {
  @override
  Stream<EngineAnalysis> analyzePosition(EngineRequest request) async* {
    yield EngineAnalysis(
      fen: request.fen,
      depth: request.targetDepth,
      lines: const [],
      isFinal: true,
    );
  }

  @override
  Future<void> cancel() async {}
  @override
  Future<void> dispose() async {}
}

void main() {
  sqfliteFfiInit();

  test(
    'temporary variation returns to immutable main line at branch',
    () async {
      final database = AppDatabase(
        factory: databaseFactoryFfi,
        databasePath: inMemoryDatabasePath,
      );
      final profile = await SqliteProfileRepository(database).create('Player');
      final games = SqliteGameRepository(database);
      await games.importPgn(
        profileId: profile.id,
        username: 'Player',
        pgn: sessionPgn,
      );
      final game = (await games.listForProfile(profile.id)).single;
      final session = AnalysisSession(
        gameId: game.id,
        database: database,
        engine: QuietEngine(),
      );
      await session.load();

      session.jumpTo(3);
      expect(session.lastMove?.san, 'Nf3');
      session.selectSquare('e7');
      session.selectSquare('e6');
      expect(session.variationBranch, 3);
      expect(session.lastMove?.san, 'e6');
      expect(session.moves[3].san, 'Nc6');

      session.previous();
      expect(session.motionFrom, 'e6');
      expect(session.motionTo, 'e7');
      expect(session.variationBranch, isNull);
      expect(session.currentPly, 3);
      session.next();
      expect(session.lastMove?.san, 'Nc6');
      await database.close();
    },
  );

  test('board defaults to the profile player color', () async {
    final database = AppDatabase(
      factory: databaseFactoryFfi,
      databasePath: inMemoryDatabasePath,
    );
    final profile = await SqliteProfileRepository(database).create('Opponent');
    final games = SqliteGameRepository(database);
    await games.importPgn(
      profileId: profile.id,
      username: 'Opponent',
      pgn: sessionPgn,
    );
    final game = (await games.listForProfile(profile.id)).single;
    final session = AnalysisSession(
      gameId: game.id,
      database: database,
      engine: QuietEngine(),
    );
    await session.load();
    expect(session.flipped, isTrue);
    session.flip();
    expect(session.flipped, isFalse);
    await database.close();
  });

  testWidgets('board renders all pieces at phone width without overflow', (
    tester,
  ) async {
    final database = AppDatabase(
      factory: databaseFactoryFfi,
      databasePath: inMemoryDatabasePath,
    );
    final session = AnalysisSession(
      gameId: 1,
      database: database,
      engine: QuietEngine(),
    );
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SizedBox(width: 390, child: ChessBoard(session: session)),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey('square-a1')), findsOneWidget);
    expect(find.byKey(const ValueKey('square-h8')), findsOneWidget);
    expect(tester.takeException(), isNull);
    await database.close();
  });
}
