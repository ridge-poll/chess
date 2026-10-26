import 'models/app_settings.dart';
import 'models/game.dart';
import 'models/profile.dart';

abstract interface class ProfileRepository {
  Future<List<Profile>> list();
  Future<Profile> create(String name);
  Future<Profile> updateSyncPreferences(
    int profileId, {
    required String username,
    required int days,
  });
}

abstract interface class GameRepository {
  Future<List<GameSummary>> listForProfile(int profileId);
  Future<void> insertFixture(int profileId);
  Future<ImportResult> importPgn({
    required int profileId,
    required String username,
    required String pgn,
    DateTime? since,
  });
}

class ImportResult {
  const ImportResult({
    required this.imported,
    required this.duplicates,
    required this.errors,
  });

  final int imported;
  final int duplicates;
  final List<String> errors;
}

abstract interface class SettingsRepository {
  Future<AppSettings> load();
  Future<void> save(AppSettings settings);
}
