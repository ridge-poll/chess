import 'package:chess_analytics_mobile/analytics/critical_moments.dart';
import 'package:chess_analytics_mobile/analytics/move_metrics.dart';
import 'package:chess_analytics_mobile/analytics/performance_estimator.dart';
import 'package:chess_analytics_mobile/data/local/app_database.dart';
import 'package:chess_analytics_mobile/data/repositories/sqlite_game_repository.dart';
import 'package:chess_analytics_mobile/data/repositories/sqlite_profile_repository.dart';
import 'package:chess_analytics_mobile/services/chess_engine.dart';
import 'package:chess_analytics_mobile/services/full_game_analyzer.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

const pgn = '''
[Event "Analysis fixture"]
[Site "fixture-analytics"]
[Date "2026.10.26"]
[White "Ridge"]
[Black "Opponent"]
[Result "1-0"]
[WhiteElo "1800"]
[BlackElo "1800"]
[TimeControl "600"]

1. e4 e5 2. Nf3 Nc6 3. Bc4 Nf6 4. d3 Bc5 5. Nc3 d6 1-0
''';

class FixtureEngine implements ChessEngine {
  FixtureEngine(this.scores, this.bestMoves);
  final Map<String, int> scores;
  final Map<String, String> bestMoves;
  int calls = 0;

  @override
  Stream<EngineAnalysis> analyzePosition(EngineRequest request) async* {
    calls++;
    final best = bestMoves[request.fen] ?? 'a2a3';
    yield EngineAnalysis(
      fen: request.fen,
      depth: request.targetDepth,
      isFinal: true,
      lines: [
        EngineLine(
          rank: 1,
          depth: request.targetDepth,
          evaluationCp: scores[request.fen] ?? 0,
          pv: [best],
        ),
        EngineLine(
          rank: 2,
          depth: request.targetDepth,
          evaluationCp: (scores[request.fen] ?? 0) - 20,
          pv: const ['h2h3'],
        ),
      ],
    );
  }

  @override
  Future<void> cancel() async {}
  @override
  Future<void> dispose() async {}
}

void main() {
  sqfliteFfiInit();

  test('metric rules match reference thresholds and mate handling', () {
    expect(classifyMove(0, 'e2e4', 'e2e4'), MoveClassification.best);
    expect(classifyMove(29, 'e2e4', 'd2d4'), MoveClassification.great);
    expect(classifyMove(30, 'e2e4', 'd2d4'), MoveClassification.good);
    expect(classifyMove(80, 'e2e4', 'd2d4'), MoveClassification.inaccuracy);
    expect(classifyMove(150, 'e2e4', 'd2d4'), MoveClassification.mistake);
    expect(classifyMove(300, 'e2e4', 'd2d4'), MoveClassification.blunder);
    expect(
      moveLoss(
        beforeCp: 500,
        afterCp: null,
        mateBefore: null,
        mateAfter: 0,
        color: 'white',
        isCheckmateAfter: true,
      ),
      0,
    );
    expect(
      moveLoss(
        beforeCp: null,
        afterCp: null,
        mateBefore: 1,
        mateAfter: -1,
        color: 'white',
      ),
      maxStatisticalCpl,
    );
    expect(accuracyFromAcpl(90), 70);
  });

  test(
    'performance estimator separates clean play and declines short samples',
    () {
      final clean = estimatePerformance(
        losses: List.filled(12, 8),
        timeClass: 'Rapid',
        ownRating: 1800,
        opponentRating: 1800,
      );
      final noisy = estimatePerformance(
        losses: [80, 20, 250, 70, 10, 330, 45, 95, 160, 40, 70, 25],
        timeClass: 'Rapid',
        ownRating: 1800,
        opponentRating: 1800,
      );
      expect(clean.rating, greaterThan(noisy.rating!));
      expect(
        estimatePerformance(losses: [0, 5, 0], timeClass: 'Blitz').rating,
        isNull,
      );
    },
  );

  test(
    'full-game analysis persists progress, accuracy, moments, and skips rerun',
    () async {
      final database = AppDatabase(
        factory: databaseFactoryFfi,
        databasePath: inMemoryDatabasePath,
      );
      final profiles = SqliteProfileRepository(database);
      final games = SqliteGameRepository(database);
      final profile = await profiles.create('Ridge');
      final imported = await games.importPgn(
        profileId: profile.id,
        username: 'Ridge',
        pgn: pgn,
      );
      final game = (await games.listForProfile(profile.id)).single;
      expect(imported.imported, 1);
      final connection = await database.instance;
      final moves = await connection.query(
        'moves',
        where: 'game_id = ?',
        whereArgs: [game.id],
        orderBy: 'ply',
      );
      final scores = <String, int>{moves.first['fen_before']! as String: 0};
      final best = <String, String>{};
      for (final move in moves) {
        scores[move['fen_after']! as String] = (move['ply'] as int) == 9
            ? -400
            : ((move['ply'] as int) > 9 ? -400 : 0);
        best[move['fen_before']! as String] = (move['ply'] as int) == 9
            ? 'd1e2'
            : move['uci']! as String;
      }
      final engine = FixtureEngine(scores, best);
      final analyzer = FullGameAnalyzer(database: database, engine: engine);
      final first = await analyzer.analyze(game.id);
      expect(first.status, 'complete');
      expect(first.analyzedPlies, moves.length);
      expect(
        await connection.query(
          'move_analyses',
          where: 'game_id = ?',
          whereArgs: [game.id],
        ),
        hasLength(moves.length),
      );
      expect(
        await connection.query(
          'critical_moments',
          where: 'game_id = ?',
          whereArgs: [game.id],
        ),
        isNotEmpty,
      );
      final updated = (await games.listForProfile(profile.id)).single;
      expect(updated.accuracy, isNotNull);
      final calls = engine.calls;
      final second = await analyzer.analyze(game.id);
      expect(second.skipped, isTrue);
      expect(engine.calls, calls);
      await database.close();
    },
  );

  test('critical moments preserve positive and negative review targets', () {
    final decisions = [
      AnalyzedDecision(
        ply: 1,
        color: 'white',
        san: 'e4',
        playedUci: 'e2e4',
        bestUci: 'e2e4',
        fenBefore: 'a',
        fenAfter: 'b',
        loss: 0,
        classification: MoveClassification.best,
        candidates: const [
          EngineLine(rank: 1, depth: 10, evaluationCp: 180, pv: ['e2e4']),
          EngineLine(rank: 2, depth: 10, evaluationCp: 10, pv: ['d2d4']),
        ],
      ),
      const AnalyzedDecision(
        ply: 5,
        color: 'white',
        san: 'h3',
        playedUci: 'h2h3',
        bestUci: 'd2d4',
        fenBefore: 'c',
        fenAfter: 'd',
        loss: 430,
        classification: MoveClassification.blunder,
        candidates: [],
      ),
    ];
    expect(findCriticalMoments(decisions, 'white').map((item) => item.type), [
      'Only Move',
      'Blunder',
    ]);
  });
}
