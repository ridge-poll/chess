import 'package:sqflite/sqflite.dart';

import '../../services/chess_engine.dart';
import '../local/app_database.dart';

class EngineCacheRepository {
  const EngineCacheRepository(this.database);
  final AppDatabase database;

  Future<EngineAnalysis?> strongest(String fen, int multiPv) async {
    final connection = await database.instance;
    final maximum = await connection.rawQuery(
      'SELECT MAX(depth) AS depth FROM position_analysis WHERE fen = ?',
      [fen],
    );
    final depth = maximum.single['depth'] as int?;
    if (depth == null) return null;
    final rows = await connection.query(
      'position_analysis',
      where: 'fen = ? AND depth = ? AND multipv <= ?',
      whereArgs: [fen, depth, multiPv],
      orderBy: 'multipv ASC',
    );
    if (rows.isEmpty) return null;
    return EngineAnalysis(
      fen: fen,
      depth: depth,
      fromCache: true,
      isFinal: false,
      lines: rows
          .map(
            (row) => EngineLine(
              rank: row['multipv']! as int,
              depth: row['depth']! as int,
              evaluationCp: row['evaluation_cp'] as int?,
              mate: row['mate'] as int?,
              pv: ((row['pv_uci'] as String?) ?? '')
                  .split(' ')
                  .where((move) => move.isNotEmpty)
                  .toList(),
            ),
          )
          .toList(),
    );
  }

  Future<void> store(EngineAnalysis analysis) async {
    final connection = await database.instance;
    final batch = connection.batch();
    for (final line in analysis.lines) {
      batch.insert('position_analysis', {
        'fen': analysis.fen,
        'depth': line.depth,
        'multipv': line.rank,
        'evaluation_cp': line.evaluationCp,
        'mate': line.mate,
        'best_move_uci': line.bestMoveUci,
        'pv_uci': line.pv.join(' '),
        'analyzed_at': DateTime.now().toUtc().toIso8601String(),
      }, conflictAlgorithm: ConflictAlgorithm.replace);
    }
    await batch.commit(noResult: true);
  }
}
