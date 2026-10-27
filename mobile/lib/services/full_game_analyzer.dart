import 'dart:convert';

import 'package:chess/chess.dart' as chess;
import 'package:sqflite/sqflite.dart';

import '../analytics/critical_moments.dart';
import '../analytics/move_metrics.dart';
import '../analytics/performance_estimator.dart';
import '../data/local/app_database.dart';
import 'chess_engine.dart';

class GameAnalysisResult {
  const GameAnalysisResult({
    required this.gameId,
    required this.status,
    required this.analyzedPlies,
    required this.totalPlies,
    required this.skipped,
  });
  final int gameId;
  final String status;
  final int analyzedPlies;
  final int totalPlies;
  final bool skipped;
}

class FullGameAnalyzer {
  const FullGameAnalyzer({required this.database, required this.engine});
  final AppDatabase database;
  final ChessEngine engine;

  Future<GameAnalysisResult> analyze(
    int gameId, {
    AnalysisBudget budget = AnalysisBudget.fast,
  }) async {
    final connection = await database.instance;
    final games = await connection.query(
      'games',
      where: 'id = ?',
      whereArgs: [gameId],
      limit: 1,
    );
    if (games.isEmpty) throw StateError('Game $gameId was not found.');
    final game = games.single;
    final moves = await connection.query(
      'moves',
      where: 'game_id = ?',
      whereArgs: [gameId],
      orderBy: 'ply ASC',
    );
    final depth = EngineRequest(fen: '', budget: budget).targetDepth;
    final existing = await _analyzedCount(connection, gameId, depth);
    if (existing >= moves.length) {
      return GameAnalysisResult(
        gameId: gameId,
        status: 'complete',
        analyzedPlies: existing,
        totalPlies: moves.length,
        skipped: true,
      );
    }
    await _job(connection, gameId, depth, 'running', existing, moves.length);
    try {
      for (final move in moves) {
        final ply = move['ply']! as int;
        final already = await connection.query(
          'move_analyses',
          columns: ['ply'],
          where: 'game_id = ? AND ply = ? AND depth = ?',
          whereArgs: [gameId, ply, depth],
          limit: 1,
        );
        if (already.isNotEmpty) continue;
        final before = await engine
            .analyzePosition(
              EngineRequest(fen: move['fen_before']! as String, budget: budget),
            )
            .last;
        final after = await engine
            .analyzePosition(
              EngineRequest(fen: move['fen_after']! as String, budget: budget),
            )
            .last;
        final best = before.lines.isEmpty ? null : before.lines.first;
        final afterBest = after.lines.isEmpty ? null : after.lines.first;
        final color = ply.isOdd ? 'white' : 'black';
        final loss = moveLoss(
          beforeCp: best?.evaluationCp,
          afterCp: afterBest?.evaluationCp,
          mateBefore: best?.mate,
          mateAfter: afterBest?.mate,
          color: color,
          isCheckmateAfter: chess.Chess.fromFEN(move['fen_after']! as String)
              .in_checkmate,
        );
        if (loss == null) continue;
        final classification = classifyMove(
          loss,
          move['uci'] as String?,
          best?.bestMoveUci,
        );
        await connection.insert('move_analyses', {
          'game_id': gameId,
          'ply': ply,
          'depth': depth,
          'played_uci': move['uci'],
          'best_uci': best?.bestMoveUci,
          'eval_before_cp': best?.evaluationCp,
          'eval_after_cp': afterBest?.evaluationCp,
          'mate_before': best?.mate,
          'mate_after': afterBest?.mate,
          'centipawn_loss': loss,
          'classification': classification.name,
          'candidates_json': jsonEncode(before.lines.map(_lineToJson).toList()),
        });
        final count = await _analyzedCount(connection, gameId, depth);
        await _job(connection, gameId, depth, 'running', count, moves.length);
      }
      await _finalize(connection, game, moves, gameId, depth);
      final count = await _analyzedCount(connection, gameId, depth);
      await _job(
        connection,
        gameId,
        depth,
        count >= moves.length ? 'complete' : 'partial',
        count,
        moves.length,
      );
      return GameAnalysisResult(
        gameId: gameId,
        status: count >= moves.length ? 'complete' : 'partial',
        analyzedPlies: count,
        totalPlies: moves.length,
        skipped: false,
      );
    } catch (error) {
      await _job(
        connection,
        gameId,
        depth,
        'failed',
        await _analyzedCount(connection, gameId, depth),
        moves.length,
        error: error.toString(),
      );
      rethrow;
    }
  }

  Map<String, Object?> _lineToJson(EngineLine line) => {
    'rank': line.rank,
    'depth': line.depth,
    'evaluation_cp': line.evaluationCp,
    'mate': line.mate,
    'pv': line.pv,
  };

  Future<void> _finalize(
    Database connection,
    Map<String, Object?> game,
    List<Map<String, Object?>> moves,
    int gameId,
    int depth,
  ) async {
    final rows = await connection.query(
      'move_analyses',
      where: 'game_id = ? AND depth = ?',
      whereArgs: [gameId, depth],
      orderBy: 'ply ASC',
    );
    final moveByPly = {for (final move in moves) move['ply'] as int: move};
    final decisions = rows.map((row) {
      final move = moveByPly[row['ply']]!;
      final candidates =
          (jsonDecode((row['candidates_json'] as String?) ?? '[]') as List)
              .cast<Map<String, dynamic>>()
              .map(
                (line) => EngineLine(
                  rank: line['rank'] as int,
                  depth: line['depth'] as int,
                  evaluationCp: line['evaluation_cp'] as int?,
                  mate: line['mate'] as int?,
                  pv: (line['pv'] as List).cast<String>(),
                ),
              )
              .toList();
      return AnalyzedDecision(
        ply: row['ply']! as int,
        color: (row['ply']! as int).isOdd ? 'white' : 'black',
        san: move['san']! as String,
        playedUci: row['played_uci']! as String,
        bestUci: row['best_uci'] as String?,
        fenBefore: move['fen_before']! as String,
        fenAfter: move['fen_after']! as String,
        loss: row['centipawn_loss']! as int,
        classification: MoveClassification.values.byName(
          row['classification']! as String,
        ),
        candidates: candidates,
      );
    }).toList();
    final moments = findCriticalMoments(
      decisions,
      game['player_color']! as String,
    );
    await connection.delete(
      'critical_moments',
      where: 'game_id = ? AND depth = ?',
      whereArgs: [gameId, depth],
    );
    for (final moment in moments) {
      await connection.insert('critical_moments', {
        'game_id': gameId,
        'ply': moment.decision.ply,
        'depth': depth,
        'polarity': moment.polarity,
        'moment_type': moment.type,
        'score': moment.score,
        'explanation': moment.explanation,
      });
    }
    final whiteLosses = decisions
        .where((item) => item.color == 'white')
        .map((item) => item.loss)
        .toList();
    final blackLosses = decisions
        .where((item) => item.color == 'black')
        .map((item) => item.loss)
        .toList();
    final white = estimatePerformance(
      losses: whiteLosses,
      timeClass: game['time_class']! as String,
      ownRating: game['white_elo'] as int?,
      opponentRating: game['black_elo'] as int?,
    );
    final black = estimatePerformance(
      losses: blackLosses,
      timeClass: game['time_class']! as String,
      ownRating: game['black_elo'] as int?,
      opponentRating: game['white_elo'] as int?,
    );
    final playerLosses = decisions
        .where((item) => item.color == game['player_color'])
        .map((item) => item.loss)
        .toList();
    final acpl = playerLosses.isEmpty
        ? null
        : playerLosses.reduce((a, b) => a + b) / playerLosses.length;
    await connection.update(
      'games',
      {
        'accuracy': accuracyFromAcpl(acpl),
        'estimated_white': white.rating,
        'estimated_black': black.rating,
        'performance_version': performanceEstimatorVersion,
      },
      where: 'id = ?',
      whereArgs: [gameId],
    );
  }

  Future<int> _analyzedCount(Database database, int gameId, int depth) async =>
      Sqflite.firstIntValue(
        await database.rawQuery(
          'SELECT COUNT(*) FROM move_analyses WHERE game_id = ? AND depth = ?',
          [gameId, depth],
        ),
      ) ??
      0;

  Future<void> _job(
    Database database,
    int gameId,
    int depth,
    String status,
    int analyzed,
    int total, {
    String? error,
  }) => database.insert('analysis_jobs', {
    'game_id': gameId,
    'depth': depth,
    'status': status,
    'analyzed_plies': analyzed,
    'total_plies': total,
    'error': error,
    'updated_at': DateTime.now().toUtc().toIso8601String(),
  }, conflictAlgorithm: ConflictAlgorithm.replace);
}
