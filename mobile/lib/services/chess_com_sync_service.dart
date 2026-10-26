abstract interface class ChessComSyncService {
  Future<SyncResult> sync({
    required int profileId,
    required String username,
    required int days,
    required bool force,
  });
}

class SyncResult {
  const SyncResult({
    required this.imported,
    required this.duplicates,
    required this.errors,
    required this.archives,
  });

  final int imported;
  final int duplicates;
  final List<String> errors;
  final int archives;

  bool get succeeded => errors.isEmpty;
}
