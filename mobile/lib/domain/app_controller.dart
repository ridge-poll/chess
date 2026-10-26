import 'package:flutter/foundation.dart';

import 'models/app_settings.dart';
import 'models/game.dart';
import 'models/profile.dart';
import 'repositories.dart';

enum LoadState { idle, loading, ready, failure }

class AppController extends ChangeNotifier {
  AppController({
    required this.profileRepository,
    required this.gameRepository,
    required this.settingsRepository,
  });
  final ProfileRepository profileRepository;
  final GameRepository gameRepository;
  final SettingsRepository settingsRepository;

  LoadState state = LoadState.idle;
  AppSettings settings = const AppSettings();
  List<Profile> availableProfiles = const [];
  List<GameSummary> profileGames = const [];
  String? errorMessage;

  Profile? get activeProfile {
    for (final profile in availableProfiles) {
      if (profile.id == settings.activeProfileId) return profile;
    }
    return null;
  }

  Future<void> initialize() async {
    state = LoadState.loading;
    notifyListeners();
    try {
      settings = await settingsRepository.load();
      availableProfiles = await profileRepository.list();
      if (availableProfiles.isEmpty) {
        availableProfiles = [await profileRepository.create('Player')];
      }
      final selected =
          availableProfiles.any(
            (profile) => profile.id == settings.activeProfileId,
          )
          ? settings.activeProfileId
          : availableProfiles.first.id;
      settings = settings.copyWith(activeProfileId: selected);
      await settingsRepository.save(settings);
      await _loadGames();
      state = LoadState.ready;
    } catch (error) {
      errorMessage = error.toString();
      state = LoadState.failure;
    }
    notifyListeners();
  }

  Future<void> selectProfile(int id) async {
    settings = settings.copyWith(activeProfileId: id);
    await settingsRepository.save(settings);
    await _loadGames();
    notifyListeners();
  }

  Future<void> createProfile(String name) async {
    final trimmed = name.trim();
    if (trimmed.isEmpty) return;
    final profile = await profileRepository.create(trimmed);
    availableProfiles = [...availableProfiles, profile];
    await selectProfile(profile.id);
  }

  Future<void> addFixtureGame() async {
    final profile = activeProfile;
    if (profile == null) return;
    await gameRepository.insertFixture(profile.id);
    await _loadGames();
    notifyListeners();
  }

  Future<void> toggleTheme() async {
    settings = settings.copyWith(darkMode: !settings.darkMode);
    await settingsRepository.save(settings);
    notifyListeners();
  }

  Future<void> setSyncDays(int value) async {
    settings = settings.copyWith(syncDays: value);
    await settingsRepository.save(settings);
    notifyListeners();
  }

  Future<void> _loadGames() async {
    final profile = activeProfile;
    profileGames = profile == null
        ? const []
        : await gameRepository.listForProfile(profile.id);
  }
}
