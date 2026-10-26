abstract interface class ChessComSyncService {
  Future<void> sync({
    required int profileId,
    required String username,
    required int days,
    required bool force,
  });
}

class ChessComSyncUnavailable implements ChessComSyncService {
  @override
  Future<void> sync({
    required int profileId,
    required String username,
    required int days,
    required bool force,
  }) {
    throw UnsupportedError('Direct Chess.com sync arrives in checkpoint 2.');
  }
}
