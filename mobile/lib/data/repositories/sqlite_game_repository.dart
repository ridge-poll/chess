import 'package:sqflite/sqflite.dart';

import '../../domain/models/game.dart';
import '../../domain/repositories.dart';
import '../import/pgn_importer.dart';
import '../local/app_database.dart';

class SqliteGameRepository implements GameRepository {
  const SqliteGameRepository(this.database, {PgnImporter? importer})
    : importer = importer ?? const PgnImporter();
  final AppDatabase database;
  final PgnImporter importer;

  @override
  Future<List<GameSummary>> listForProfile(int profileId) async {
    final rows = await (await database.instance).query(
      'games',
      where: 'profile_id = ?',
      whereArgs: [profileId],
      orderBy: 'played_at DESC',
    );
    return rows.map(GameSummary.fromMap).toList(growable: false);
  }

  @override
  Future<void> insertFixture(int profileId) async {
    final connection = await database.instance;
    final stamp = DateTime.now().toUtc();
    final fingerprint = 'fixture-$profileId-${stamp.microsecondsSinceEpoch}';
    await connection.insert('games', {
      'profile_id': profileId,
      'fingerprint': fingerprint,
      'played_at': stamp.toIso8601String(),
      'white': 'LocalPlayer',
      'black': 'SampleOpponent',
      'white_elo': 1420,
      'black_elo': 1457,
      'player_color': 'white',
      'result': '1-0',
      'opening': "Queen's Gambit Declined",
      'time_class': 'Rapid',
      'accuracy': 86.4,
      'pgn': '[White "LocalPlayer"]\n[Black "SampleOpponent"]\n[Result "1-0"]\n\n1. d4 d5 2. c4 e6 3. Nc3 Nf6 1-0',
      'created_at': stamp.toIso8601String(),
    });
  }

  @override
  Future<ImportResult> importPgn({
    required int profileId,
    required String username,
    required String pgn,
    DateTime? since,
  }) async {
    final parsed = importer.parse(pgn, since: since);
    var imported = 0;
    var duplicates = 0;
    final connection = await database.instance;
    for (final game in parsed.games) {
      try {
        await connection.transaction((transaction) async {
          final headers = game.headers;
          final white = headers['White'] ?? 'Unknown';
          final black = headers['Black'] ?? 'Unknown';
          final normalizedUser = username.trim().toLowerCase();
          final playerColor = white.toLowerCase() == normalizedUser
              ? 'white'
              : black.toLowerCase() == normalizedUser
              ? 'black'
              : 'unknown';
          final gameId = await transaction.insert('games', {
            'profile_id': profileId,
            'fingerprint': game.fingerprint,
            'played_at': game.playedAt.toIso8601String(),
            'white': white,
            'black': black,
            'white_elo': int.tryParse(headers['WhiteElo'] ?? ''),
            'black_elo': int.tryParse(headers['BlackElo'] ?? ''),
            'player_color': playerColor,
            'result': headers['Result'] ?? '*',
            'event': headers['Event'],
            'site': headers['Site'],
            'eco': headers['ECO'],
            'opening': headers['Opening'],
            'time_control': headers['TimeControl'],
            'time_class': classifyTimeControl(headers['TimeControl']),
            'ply_count': game.moves.length,
            'pgn': game.rawPgn,
            'created_at': DateTime.now().toUtc().toIso8601String(),
          });
          final batch = transaction.batch();
          for (final move in game.moves) {
            batch.insert('moves', {
              'game_id': gameId,
              'ply': move.ply,
              'san': move.san,
              'uci': move.uci,
              'fen_before': move.fenBefore,
              'fen_after': move.fenAfter,
            });
          }
          await batch.commit(noResult: true);
        });
        imported++;
      } on DatabaseException catch (error) {
        if (error.isUniqueConstraintError()) {
          duplicates++;
        } else {
          rethrow;
        }
      }
    }
    return ImportResult(
      imported: imported,
      duplicates: duplicates,
      errors: parsed.errors,
    );
  }
}
