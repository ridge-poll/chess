import 'package:flutter/material.dart';

import 'app/app.dart';
import 'data/local/app_database.dart';
import 'data/repositories/preferences_settings_repository.dart';
import 'data/repositories/sqlite_game_repository.dart';
import 'data/repositories/sqlite_profile_repository.dart';
import 'domain/app_controller.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final database = AppDatabase();
  final controller = AppController(
    profileRepository: SqliteProfileRepository(database),
    gameRepository: SqliteGameRepository(database),
    settingsRepository: PreferencesSettingsRepository(),
  );
  runApp(ChessAnalyticsApp(controller: controller));
  await controller.initialize();
}
