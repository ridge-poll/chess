import '../analytics/move_metrics.dart';
import '../data/local/app_database.dart';

class DiagnosticMove {
  const DiagnosticMove({
    required this.ply,
    required this.san,
    required this.uci,
    required this.fenAfter,
    required this.color,
    required this.phase,
    required this.openness,
    this.clockMs,
    this.timeSpentMs,
    this.evaluationCp,
    this.loss,
    this.classification,
  });

  final int ply;
  final String san;
  final String uci;
  final String fenAfter;
  final String color;
  final String phase;
  final double openness;
  final int? clockMs;
  final int? timeSpentMs;
  final int? evaluationCp;
  final int? loss;
  final MoveClassification? classification;
}

class CriticalDiagnostic {
  const CriticalDiagnostic({
    required this.ply,
    required this.san,
    required this.polarity,
    required this.type,
    required this.score,
    required this.explanation,
  });
  final int ply;
  final String san;
  final String polarity;
  final String type;
  final double score;
  final String explanation;
}

class PhaseDiagnostic {
  const PhaseDiagnostic(this.name, this.averageLoss, this.moveCount);
  final String name;
  final double? averageLoss;
  final int moveCount;
}

class GameDiagnostics {
  const GameDiagnostics({
    required this.gameId,
    required this.white,
    required this.black,
    required this.playerColor,
    required this.result,
    required this.timeClass,
    required this.moves,
    required this.criticalMoments,
    required this.qualityCounts,
    required this.phases,
    this.whiteElo,
    this.blackElo,
    this.opening,
    this.timeControl,
    this.accuracy,
    this.estimatedWhite,
    this.estimatedBlack,
  });
  final int gameId;
  final String white;
  final String black;
  final String playerColor;
  final String result;
  final String timeClass;
  final int? whiteElo;
  final int? blackElo;
  final String? opening;
  final String? timeControl;
  final double? accuracy;
  final int? estimatedWhite;
  final int? estimatedBlack;
  final List<DiagnosticMove> moves;
  final List<CriticalDiagnostic> criticalMoments;
  final Map<MoveClassification, int> qualityCounts;
  final List<PhaseDiagnostic> phases;

  String get userName => playerColor == 'black' ? black : white;
  String get opponentName => playerColor == 'black' ? white : black;
  int? get userElo => playerColor == 'black' ? blackElo : whiteElo;
  int? get opponentElo => playerColor == 'black' ? whiteElo : blackElo;
  int? get estimatedUser =>
      playerColor == 'black' ? estimatedBlack : estimatedWhite;
  int? get estimatedOpponent =>
      playerColor == 'black' ? estimatedWhite : estimatedBlack;
}

class GameDiagnosticsRepository {
  const GameDiagnosticsRepository(this.database);
  final AppDatabase database;

  Future<GameDiagnostics> load(int gameId) async {
    final db = await database.instance;
    final games = await db.query(
      'games',
      where: 'id = ?',
      whereArgs: [gameId],
      limit: 1,
    );
    if (games.isEmpty) throw StateError('Game $gameId was not found.');
    final game = games.single;
    final depth =
        (await db.rawQuery(
              'SELECT MAX(depth) AS depth FROM move_analyses WHERE game_id = ?',
              [gameId],
            )).single['depth']
            as int?;
    final rows = await db.rawQuery(
      '''
      SELECT m.*, ma.eval_after_cp, ma.mate_after,
             ma.centipawn_loss, ma.classification
      FROM moves m
      LEFT JOIN move_analyses ma
        ON ma.game_id = m.game_id AND ma.ply = m.ply AND ma.depth = ?
      WHERE m.game_id = ? ORDER BY m.ply
    ''',
      [depth ?? -1, gameId],
    );
    final increment = _incrementSeconds(game['time_control'] as String?);
    final previousClock = <String, int>{};
    final moves = <DiagnosticMove>[];
    for (final row in rows) {
      final ply = row['ply']! as int;
      final color = ply.isOdd ? 'white' : 'black';
      final clock = row['clock_ms'] as int?;
      final prior = previousClock[color];
      final spent = clock == null || prior == null
          ? null
          : (prior + increment * 1000 - clock).clamp(0, 3600000);
      if (clock != null) previousClock[color] = clock;
      final fen = row['fen_after']! as String;
      moves.add(
        DiagnosticMove(
          ply: ply,
          san: row['san']! as String,
          uci: row['uci']! as String,
          fenAfter: fen,
          color: color,
          phase: _phase(fen, ply),
          openness: opennessFromFen(fen),
          clockMs: clock,
          timeSpentMs: spent,
          evaluationCp: scoreToCp(
            row['eval_after_cp'] as int?,
            row['mate_after'] as int?,
          ),
          loss: row['centipawn_loss'] as int?,
          classification: _classification(row['classification'] as String?),
        ),
      );
    }
    final criticalRows = await db.rawQuery(
      '''
      SELECT cm.*, m.san FROM critical_moments cm
      JOIN moves m ON m.game_id = cm.game_id AND m.ply = cm.ply
      WHERE cm.game_id = ? AND cm.depth = ? ORDER BY cm.ply
    ''',
      [gameId, depth ?? -1],
    );
    final critical = criticalRows
        .map(
          (row) => CriticalDiagnostic(
            ply: row['ply']! as int,
            san: row['san']! as String,
            polarity: row['polarity']! as String,
            type: row['moment_type']! as String,
            score: (row['score']! as num).toDouble(),
            explanation: row['explanation']! as String,
          ),
        )
        .toList();
    final counts = {for (final value in MoveClassification.values) value: 0};
    for (final move in moves) {
      if (move.classification case final classification?) {
        counts[classification] = counts[classification]! + 1;
      }
    }
    final playerColor = game['player_color']! as String;
    final phases = ['Opening', 'Middlegame', 'Endgame'].map((name) {
      final losses = moves
          .where((move) => move.color == playerColor && move.phase == name)
          .map((move) => move.loss)
          .whereType<int>()
          .toList();
      return PhaseDiagnostic(
        name,
        losses.isEmpty ? null : losses.reduce((a, b) => a + b) / losses.length,
        losses.length,
      );
    }).toList();
    return GameDiagnostics(
      gameId: gameId,
      white: game['white']! as String,
      black: game['black']! as String,
      playerColor: playerColor,
      result: game['result']! as String,
      timeClass: game['time_class']! as String,
      whiteElo: game['white_elo'] as int?,
      blackElo: game['black_elo'] as int?,
      opening: game['opening'] as String?,
      timeControl: game['time_control'] as String?,
      accuracy: (game['accuracy'] as num?)?.toDouble(),
      estimatedWhite: game['estimated_white'] as int?,
      estimatedBlack: game['estimated_black'] as int?,
      moves: moves,
      criticalMoments: critical,
      qualityCounts: counts,
      phases: phases,
    );
  }

  static MoveClassification? _classification(String? value) {
    if (value == null) return null;
    for (final item in MoveClassification.values) {
      if (item.name == value) return item;
    }
    return null;
  }

  static int _incrementSeconds(String? timeControl) {
    final parts = timeControl?.split('+');
    return parts?.length == 2 ? int.tryParse(parts![1]) ?? 0 : 0;
  }

  static String _phase(String fen, int ply) {
    if (ply <= 20) return 'Opening';
    final board = fen.split(' ').first;
    final heavyMinor = RegExp(r'[qQrRbBnN]').allMatches(board).length;
    final fullmove = int.tryParse(fen.split(' ').elementAtOrNull(5) ?? '') ?? 1;
    return heavyMinor <= 6 || fullmove >= 40 ? 'Endgame' : 'Middlegame';
  }
}

double opennessFromFen(String fen) {
  final ranks = fen.split(' ').first.split('/');
  final files = List.generate(8, (_) => <String>[]);
  var pawns = 0;
  var centralPawns = 0;
  for (var rank = 0; rank < ranks.length; rank++) {
    var file = 0;
    for (final rune in ranks[rank].runes) {
      final char = String.fromCharCode(rune);
      final empty = int.tryParse(char);
      if (empty != null) {
        file += empty;
      } else {
        files[file].add(char);
        if (char.toLowerCase() == 'p') {
          pawns++;
          if (file >= 2 && file <= 5 && rank >= 2 && rank <= 5) {
            centralPawns++;
          }
        }
        file++;
      }
    }
  }
  final openFiles = files
      .where((pieces) => !pieces.any((piece) => piece.toLowerCase() == 'p'))
      .length;
  final pawnClearance = (16 - pawns) / 16;
  final centerClearance = (8 - centralPawns).clamp(0, 8) / 8;
  return (.5 * pawnClearance + .3 * openFiles / 8 + .2 * centerClearance).clamp(
    0,
    1,
  );
}
