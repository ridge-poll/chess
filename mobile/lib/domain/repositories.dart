import 'models/app_settings.dart';
import 'models/game.dart';
import 'models/profile.dart';

abstract interface class ProfileRepository {
  Future<List<Profile>> list();
  Future<Profile> create(String name);
}

abstract interface class GameRepository {
  Future<List<GameSummary>> listForProfile(int profileId);
  Future<void> insertFixture(int profileId);
}

abstract interface class SettingsRepository {
  Future<AppSettings> load();
  Future<void> save(AppSettings settings);
}
