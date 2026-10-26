import 'dart:convert';

import 'package:chess_analytics_mobile/data/import/pgn_importer.dart';
import 'package:chess_analytics_mobile/data/local/app_database.dart';
import 'package:chess_analytics_mobile/data/repositories/sqlite_game_repository.dart';
import 'package:chess_analytics_mobile/data/repositories/sqlite_profile_repository.dart';
import 'package:chess_analytics_mobile/services/chess_com_sync_client.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

const samplePgn = '''
[Event "Live Chess"]
[Site "https://www.chess.com/game/live/123"]
[Date "2026.10.25"]
[UTCDate "2026.10.25"]
[UTCTime "18:30:00"]
[White "RidgePoll1"]
[Black "Opponent"]
[Result "1-0"]
[WhiteElo "1812"]
[BlackElo "1798"]
[TimeControl "600"]
[ECO "D06"]
[Opening "Queen's Gambit"]

1. d4 d5 2. c4 e6 3. Nc3 Nf6 1-0
''';

void main() {
  sqfliteFfiInit();

  test('PGN parser reconstructs ordered FEN history and metadata', () {
    final result = const PgnImporter().parse(samplePgn);

    expect(result.errors, isEmpty);
    expect(result.games, hasLength(1));
    expect(result.games.single.moves.map((move) => move.san), [
      'd4',
      'd5',
      'c4',
      'e6',
      'Nc3',
      'Nf6',
    ]);
    expect(result.games.single.moves.first.uci, 'd2d4');
    expect(result.games.single.moves.first.fenBefore, startsWith('rnbqkbnr'));
    expect(result.games.single.moves.first.fenAfter, contains(' b '));
    expect(classifyTimeControl('600'), 'Rapid');
  });

  test(
    'forced Chess.com sync imports once and preserves profile ownership',
    () async {
      final database = AppDatabase(
        factory: databaseFactoryFfi,
        databasePath: inMemoryDatabasePath,
      );
      final profiles = SqliteProfileRepository(database);
      final games = SqliteGameRepository(database);
      final ridge = await profiles.create('Ridge');
      final other = await profiles.create('Other');
      var archiveFetches = 0;
      final client = MockClient((request) async {
        if (request.url.path.endsWith('/games/archives')) {
          return http.Response(
            jsonEncode({
              'archives': [
                'https://api.chess.com/pub/player/ridgepoll1/games/2026/10',
              ],
            }),
            200,
          );
        }
        archiveFetches++;
        return http.Response(samplePgn, 200);
      });
      final sync = ChessComSyncClient(gameRepository: games, client: client);

      final first = await sync.sync(
        profileId: ridge.id,
        username: 'RidgePoll1',
        days: 365,
        force: true,
      );
      final second = await sync.sync(
        profileId: ridge.id,
        username: 'RidgePoll1',
        days: 365,
        force: true,
      );

      expect(first.imported, 1);
      expect(second.imported, 0);
      expect(second.duplicates, 1);
      expect(archiveFetches, 2, reason: 'Manual refresh always refetches PGN.');
      final imported = await games.listForProfile(ridge.id);
      expect(imported, hasLength(1));
      expect(imported.single.playerColor, 'white');
      expect(imported.single.opponent, 'Opponent');
      expect(await games.listForProfile(other.id), isEmpty);
      final moveRows = await (await database.instance).query('moves');
      expect(moveRows, hasLength(6));
      await database.close();
    },
  );

  test('PGN date window excludes older games', () {
    final result = const PgnImporter().parse(
      samplePgn,
      since: DateTime.utc(2026, 10, 26),
    );
    expect(result.games, isEmpty);
    expect(result.errors, isEmpty);
  });
}
