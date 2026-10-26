import '../../domain/models/game.dart';
import '../../domain/repositories.dart';
import '../local/app_database.dart';

class SqliteGameRepository implements GameRepository {
  const SqliteGameRepository(this.database);
  final AppDatabase database;

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
}
