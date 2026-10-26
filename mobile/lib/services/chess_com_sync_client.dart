import 'dart:convert';

import 'package:http/http.dart' as http;

import '../domain/repositories.dart';
import 'chess_com_sync_service.dart';

class ChessComSyncClient implements ChessComSyncService {
  ChessComSyncClient({required this.gameRepository, http.Client? client})
    : _client = client ?? http.Client();

  static const _baseUrl = 'https://api.chess.com/pub/player';
  static const _headers = {
    'User-Agent': 'ChessAnalyticsMobile/1.0',
    'Accept': 'application/json,text/plain',
  };

  final GameRepository gameRepository;
  final http.Client _client;

  @override
  Future<SyncResult> sync({
    required int profileId,
    required String username,
    required int days,
    required bool force,
  }) async {
    final normalized = username.trim().toLowerCase();
    if (normalized.isEmpty) {
      throw ArgumentError('Chess.com username is required.');
    }
    final safeDays = days.clamp(1, 365);
    final archiveResponse = await _get(
      Uri.parse('$_baseUrl/$normalized/games/archives'),
    );
    final decoded = jsonDecode(archiveResponse) as Map<String, dynamic>;
    final allArchives = (decoded['archives'] as List<dynamic>? ?? const [])
        .cast<String>();
    final archiveCount = ((safeDays + 30) / 31).floor().clamp(1, 12);
    final archives = allArchives.length <= archiveCount
        ? allArchives
        : allArchives.sublist(allArchives.length - archiveCount);
    final since = DateTime.now().toUtc().subtract(Duration(days: safeDays));
    var imported = 0;
    var duplicates = 0;
    final errors = <String>[];
    for (final archive in archives) {
      try {
        final pgn = await _get(Uri.parse('$archive/pgn'));
        final result = await gameRepository.importPgn(
          profileId: profileId,
          username: normalized,
          pgn: pgn,
          since: since,
        );
        imported += result.imported;
        duplicates += result.duplicates;
        errors.addAll(result.errors);
      } catch (error) {
        errors.add(error.toString());
      }
    }
    return SyncResult(
      imported: imported,
      duplicates: duplicates,
      errors: errors,
      archives: archives.length,
    );
  }

  Future<String> _get(Uri uri) async {
    final response = await _client.get(uri, headers: _headers);
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw StateError('Chess.com returned HTTP ${response.statusCode}.');
    }
    return utf8.decode(response.bodyBytes);
  }
}
