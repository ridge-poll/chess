import 'package:flutter/material.dart';

import 'app/app.dart';
import 'data/local/app_database.dart';
import 'data/repositories/preferences_settings_repository.dart';
import 'data/repositories/engine_cache_repository.dart';
import 'data/repositories/sqlite_game_repository.dart';
import 'data/repositories/sqlite_profile_repository.dart';
import 'domain/app_controller.dart';
import 'services/chess_com_sync_client.dart';
import 'services/full_game_analyzer.dart';
import 'services/local_stockfish_engine.dart';
import 'services/stockfish_transport.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final database = AppDatabase();
  final gameRepository = SqliteGameRepository(database);
  final engine = LocalStockfishEngine(
    transport: NativeStockfishTransport(),
    cache: EngineCacheRepository(database),
  );
  final controller = AppController(
    profileRepository: SqliteProfileRepository(database),
    gameRepository: gameRepository,
    settingsRepository: PreferencesSettingsRepository(),
    syncService: ChessComSyncClient(gameRepository: gameRepository),
    gameAnalyzer: FullGameAnalyzer(database: database, engine: engine),
  );
  runApp(ChessAnalyticsApp(controller: controller));
  await controller.initialize();
}
