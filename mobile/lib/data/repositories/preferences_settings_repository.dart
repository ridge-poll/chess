import 'package:shared_preferences/shared_preferences.dart';

import '../../domain/models/app_settings.dart';
import '../../domain/repositories.dart';

class PreferencesSettingsRepository implements SettingsRepository {
  static const _profileKey = 'active_profile_id';
  static const _darkModeKey = 'dark_mode';
  static const _syncDaysKey = 'sync_days';

  @override
  Future<AppSettings> load() async {
    final preferences = await SharedPreferences.getInstance();
    return AppSettings(
      activeProfileId: preferences.getInt(_profileKey),
      darkMode: preferences.getBool(_darkModeKey) ?? true,
      syncDays: preferences.getInt(_syncDaysKey) ?? 7,
    );
  }

  @override
  Future<void> save(AppSettings settings) async {
    final preferences = await SharedPreferences.getInstance();
    if (settings.activeProfileId != null) {
      await preferences.setInt(_profileKey, settings.activeProfileId!);
    }
    await preferences.setBool(_darkModeKey, settings.darkMode);
    await preferences.setInt(_syncDaysKey, settings.syncDays);
  }
}
