import 'package:chess_analytics_mobile/data/local/app_database.dart';
import 'package:chess_analytics_mobile/data/repositories/sqlite_game_repository.dart';
import 'package:chess_analytics_mobile/data/repositories/sqlite_profile_repository.dart';
import 'package:chess_analytics_mobile/domain/app_controller.dart';
import 'package:chess_analytics_mobile/domain/models/app_settings.dart';
import 'package:chess_analytics_mobile/domain/repositories.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

class MemorySettingsRepository implements SettingsRepository {
  AppSettings value = const AppSettings();

  @override
  Future<AppSettings> load() async => value;

  @override
  Future<void> save(AppSettings settings) async => value = settings;
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
