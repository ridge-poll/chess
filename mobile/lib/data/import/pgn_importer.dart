import 'dart:convert';

import 'package:chess/chess.dart' as chess;
import 'package:crypto/crypto.dart';

class ParsedPgnGame {
  const ParsedPgnGame({
    required this.headers,
    required this.rawPgn,
    required this.fingerprint,
    required this.playedAt,
    required this.moves,
  });

  final Map<String, String> headers;
  final String rawPgn;
  final String fingerprint;
  final DateTime playedAt;
  final List<ParsedPgnMove> moves;
}

class ParsedPgnMove {
  const ParsedPgnMove({
    required this.ply,
    required this.san,
    required this.uci,
    required this.fenBefore,
    required this.fenAfter,
  });

  final int ply;
  final String san;
  final String uci;
  final String fenBefore;
  final String fenAfter;
}

class PgnParseResult {
  const PgnParseResult(this.games, this.errors);
  final List<ParsedPgnGame> games;
  final List<String> errors;
}

class PgnImporter {
  const PgnImporter();

  PgnParseResult parse(String source, {DateTime? since}) {
    final games = <ParsedPgnGame>[];
    final errors = <String>[];
    final chunks = _splitGames(source);
    for (var index = 0; index < chunks.length; index++) {
      try {
        final game = _parseGame(chunks[index]);
        if (since == null || !game.playedAt.isBefore(since)) games.add(game);
      } catch (error) {
        errors.add('Game ${index + 1}: $error');
      }
    }
    return PgnParseResult(games, errors);
  }

  ParsedPgnGame _parseGame(String rawPgn) {
    final headers = <String, String>{};
    final headerPattern = RegExp(
      r'^\[([A-Za-z0-9_]+)\s+"(.*)"\]\s*$',
      multiLine: true,
    );
    for (final match in headerPattern.allMatches(rawPgn)) {
      headers[match.group(1)!] = match.group(2)!.replaceAll(r'\"', '"');
    }
    final board = chess.Chess();
    if (!board.load_pgn(rawPgn)) {
      throw const FormatException('malformed or illegal PGN moves');
    }
    final history = board.getHistory({
      'verbose': true,
    }).cast<Map<dynamic, dynamic>>();
    final replay = chess.Chess();
    final moves = <ParsedPgnMove>[];
    for (var index = 0; index < history.length; index++) {
      final move = history[index];
      final before = replay.fen;
      final san = move['san'] as String;
      if (!replay.move(san)) {
        throw FormatException('could not replay $san');
      }
      moves.add(
        ParsedPgnMove(
          ply: index + 1,
          san: san,
          uci: '${move['from']}${move['to']}',
          fenBefore: before,
          fenAfter: replay.fen,
        ),
      );
    }
    if (moves.isEmpty) throw const FormatException('game contains no moves');
    final identity = [
      headers['Site'],
      headers['UTCDate'] ?? headers['Date'],
      headers['UTCTime'],
      headers['White'],
      headers['Black'],
      headers['Result'],
      ...moves.map((move) => move.uci),
    ].join('|');
    return ParsedPgnGame(
      headers: headers,
      rawPgn: rawPgn.trim(),
      fingerprint: sha256.convert(utf8.encode(identity)).toString(),
      playedAt: _playedAt(headers),
      moves: moves,
    );
  }

  List<String> _splitGames(String source) {
    final normalized = source.replaceAll('\r\n', '\n').trim();
    if (normalized.isEmpty) return const [];
    final starts = RegExp(
      r'^\[Event\s+"',
      multiLine: true,
    ).allMatches(normalized).map((match) => match.start).toList();
    if (starts.isEmpty) return [normalized];
    return [
      for (var index = 0; index < starts.length; index++)
        normalized
            .substring(
              starts[index],
              index + 1 < starts.length ? starts[index + 1] : normalized.length,
            )
            .trim(),
    ];
  }

  DateTime _playedAt(Map<String, String> headers) {
    final date = headers['UTCDate'] ?? headers['Date'];
    if (date == null || date.contains('?')) return DateTime.now().toUtc();
    final time = headers['UTCTime'] ?? '00:00:00';
    final parsed = DateTime.tryParse('${date.replaceAll('.', '-')}T${time}Z');
    return parsed ?? DateTime.now().toUtc();
  }
}

String classifyTimeControl(String? value) {
  if (value == null || value == '?' || value == '-') return 'Unknown';
  if (value.contains('/')) return 'Daily';
  final first = value.split(':').first;
  final parts = first.split('+');
  final base = int.tryParse(parts.first);
  final increment = parts.length > 1 ? int.tryParse(parts[1]) ?? 0 : 0;
  if (base == null) return 'Unknown';
  if (base >= 86400) return 'Daily';
  final estimated = base + increment * 40;
  if (estimated < 180) return 'Bullet';
  if (estimated < 600) return 'Blitz';
  if (estimated < 3600) return 'Rapid';
  return 'Classical';
}
