class AppSettings {
  const AppSettings({
    this.activeProfileId,
    this.darkMode = true,
    this.syncDays = 7,
  });
  final int? activeProfileId;
  final bool darkMode;
  final int syncDays;

  AppSettings copyWith({int? activeProfileId, bool? darkMode, int? syncDays}) =>
      AppSettings(
        activeProfileId: activeProfileId ?? this.activeProfileId,
        darkMode: darkMode ?? this.darkMode,
        syncDays: syncDays ?? this.syncDays,
      );
}
