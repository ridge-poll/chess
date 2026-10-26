import 'package:flutter/foundation.dart';

import 'models/app_settings.dart';
import 'models/game.dart';
import 'models/profile.dart';
import 'repositories.dart';
import '../services/chess_com_sync_service.dart';

enum LoadState { idle, loading, ready, failure }

enum SyncState { idle, syncing, success, failure }

class AppController extends ChangeNotifier {
  AppController({
    required this.profileRepository,
    required this.gameRepository,
    required this.settingsRepository,
    required this.syncService,
  });
  final ProfileRepository profileRepository;
  final GameRepository gameRepository;
  final SettingsRepository settingsRepository;
  final ChessComSyncService syncService;

  LoadState state = LoadState.idle;
  AppSettings settings = const AppSettings();
  List<Profile> availableProfiles = const [];
  List<GameSummary> profileGames = const [];
  String? errorMessage;
  SyncState syncState = SyncState.idle;
  String? syncMessage;

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
    final profile = activeProfile;
    if (profile == null) return;
    await saveSyncPreferences(
      username: profile.chessComUsername ?? '',
      days: value,
    );
  }

  Future<void> saveSyncPreferences({
    required String username,
    required int days,
  }) async {
    final profile = activeProfile;
    if (profile == null) return;
    final updated = await profileRepository.updateSyncPreferences(
      profile.id,
      username: username,
      days: days.clamp(1, 365),
    );
    availableProfiles = [
      for (final item in availableProfiles)
        if (item.id == updated.id) updated else item,
    ];
    settings = settings.copyWith(syncDays: updated.syncDays);
    await settingsRepository.save(settings);
    notifyListeners();
  }

  Future<void> syncGames() async {
    final profile = activeProfile;
    if (profile == null || syncState == SyncState.syncing) return;
    final username = profile.chessComUsername?.trim() ?? '';
    if (username.isEmpty) {
      syncState = SyncState.failure;
      syncMessage = 'Add a Chess.com username in More before syncing.';
      notifyListeners();
      return;
    }
    syncState = SyncState.syncing;
    syncMessage = 'Checking Chess.com for recent games…';
    notifyListeners();
    try {
      final result = await syncService.sync(
        profileId: profile.id,
        username: username,
        days: profile.syncDays,
        force: true,
      );
      await _loadGames();
      if (result.errors.isNotEmpty && result.archives == 0) {
        syncState = SyncState.failure;
        syncMessage = result.errors.first;
      } else {
        syncState = result.errors.isEmpty
            ? SyncState.success
            : SyncState.failure;
        syncMessage = result.imported > 0
            ? 'Added ${result.imported} new ${result.imported == 1 ? 'game' : 'games'}.'
            : result.errors.isEmpty
            ? 'Games are up to date.'
            : 'Sync finished with ${result.errors.length} issue(s).';
      }
    } catch (error) {
      syncState = SyncState.failure;
      syncMessage = _friendlySyncError(error);
    }
    notifyListeners();
  }

  void clearSyncMessage() {
    syncState = SyncState.idle;
    syncMessage = null;
    notifyListeners();
  }

  String _friendlySyncError(Object error) {
    final message = error.toString().replaceFirst('Bad state: ', '');
    if (message.contains('HTTP 404')) {
      return 'Chess.com username was not found.';
    }
    return message.replaceFirst('Exception: ', '');
  }

  Future<void> _loadGames() async {
    final profile = activeProfile;
    profileGames = profile == null
        ? const []
        : await gameRepository.listForProfile(profile.id);
  }
}
