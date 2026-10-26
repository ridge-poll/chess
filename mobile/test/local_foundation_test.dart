import 'dart:io';

import 'package:chess_analytics_mobile/data/local/app_database.dart';
import 'package:chess_analytics_mobile/data/repositories/sqlite_game_repository.dart';
import 'package:chess_analytics_mobile/data/repositories/sqlite_profile_repository.dart';
import 'package:chess_analytics_mobile/domain/app_controller.dart';
import 'package:chess_analytics_mobile/domain/models/app_settings.dart';
import 'package:chess_analytics_mobile/domain/repositories.dart';
import 'package:chess_analytics_mobile/services/chess_com_sync_service.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

class MemorySettingsRepository implements SettingsRepository {
  AppSettings value = const AppSettings();

  @override
  Future<AppSettings> load() async => value;

  @override
  Future<void> save(AppSettings settings) async => value = settings;
}

class NoopSyncService implements ChessComSyncService {
  @override
  Future<SyncResult> sync({
    required int profileId,
    required String username,
    required int days,
    required bool force,
  }) async =>
      const SyncResult(imported: 0, duplicates: 0, errors: [], archives: 0);
}

void main() {
  sqfliteFfiInit();

  test('profiles and games persist locally and remain isolated', () async {
    final database = AppDatabase(
      factory: databaseFactoryFfi,
      databasePath: inMemoryDatabasePath,
    );
    final profiles = SqliteProfileRepository(database);
    final games = SqliteGameRepository(database);
    final ridge = await profiles.create('Ridge');
    final study = await profiles.create('Study');

    await games.insertFixture(ridge.id);

    expect(await games.listForProfile(ridge.id), hasLength(1));
    expect(await games.listForProfile(study.id), isEmpty);
    expect((await profiles.list()).map((profile) => profile.name), [
      'Ridge',
      'Study',
    ]);
    await database.close();
  });

  test(
    'version 1 installation upgrades without losing profiles or games',
    () async {
      final directory = await Directory.systemTemp.createTemp('chess-mobile-');
      final location = '${directory.path}/upgrade.sqlite3';
      final legacy = await databaseFactoryFfi.openDatabase(
        location,
        options: OpenDatabaseOptions(
          version: 1,
          onCreate: (database, version) async {
            await database.execute('''
            CREATE TABLE profiles (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT NOT NULL COLLATE NOCASE UNIQUE,
              created_at TEXT NOT NULL
            )
          ''');
            await database.execute('''
            CREATE TABLE games (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
              fingerprint TEXT NOT NULL,
              played_at TEXT NOT NULL,
              white TEXT NOT NULL,
              black TEXT NOT NULL,
              white_elo INTEGER,
              black_elo INTEGER,
              player_color TEXT NOT NULL,
              result TEXT NOT NULL,
              opening TEXT,
              time_class TEXT NOT NULL,
              pgn TEXT NOT NULL,
              accuracy REAL,
              created_at TEXT NOT NULL,
              UNIQUE(profile_id, fingerprint)
            )
          ''');
            await database.execute('''
            CREATE TABLE moves (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
              ply INTEGER NOT NULL,
              san TEXT NOT NULL,
              uci TEXT,
              fen_before TEXT,
              fen_after TEXT,
              clock_ms INTEGER,
              UNIQUE(game_id, ply)
            )
          ''');
            await database.execute('''
            CREATE TABLE position_analysis (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              game_id INTEGER REFERENCES games(id) ON DELETE CASCADE,
              ply INTEGER,
              fen TEXT NOT NULL,
              depth INTEGER NOT NULL,
              multipv INTEGER NOT NULL DEFAULT 1,
              evaluation_cp INTEGER,
              mate INTEGER,
              best_move_uci TEXT,
              pv_uci TEXT,
              classification TEXT,
              centipawn_loss INTEGER,
              analyzed_at TEXT NOT NULL,
              UNIQUE(fen, depth, multipv)
            )
          ''');
            await database.execute('''
            CREATE TABLE opening_cache (
              position_key TEXT PRIMARY KEY,
              response_json TEXT NOT NULL,
              fetched_at TEXT NOT NULL
            )
          ''');
            await database.insert('profiles', {
              'name': 'Returning Player',
              'created_at': DateTime.utc(2026).toIso8601String(),
            });
          },
        ),
      );
      await legacy.close();

      final upgraded = AppDatabase(
        factory: databaseFactoryFfi,
        databasePath: location,
      );
      final profiles = SqliteProfileRepository(upgraded);
      final existing = await profiles.list();
      expect(existing.single.name, 'Returning Player');
      expect(existing.single.syncDays, 7);
      await profiles.updateSyncPreferences(
        existing.single.id,
        username: 'RidgePoll1',
        days: 14,
      );
      expect((await profiles.list()).single.chessComUsername, 'ridgepoll1');
      await upgraded.close();
      await directory.delete(recursive: true);
    },
  );

  test(
    'controller restores a valid profile and profile-specific games',
    () async {
      final database = AppDatabase(
        factory: databaseFactoryFfi,
        databasePath: inMemoryDatabasePath,
      );
      final profiles = SqliteProfileRepository(database);
      final games = SqliteGameRepository(database);
      final settings = MemorySettingsRepository();
      final ridge = await profiles.create('Ridge');
      final study = await profiles.create('Study');
      await games.insertFixture(study.id);
      settings.value = AppSettings(activeProfileId: study.id);
      final controller = AppController(
        profileRepository: profiles,
        gameRepository: games,
        settingsRepository: settings,
        syncService: NoopSyncService(),
      );

      await controller.initialize();
      expect(controller.activeProfile?.name, 'Study');
      expect(controller.profileGames, hasLength(1));

      await controller.selectProfile(ridge.id);
      expect(controller.profileGames, isEmpty);
      expect(settings.value.activeProfileId, ridge.id);
      await database.close();
    },
  );
}
