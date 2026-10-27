import 'dart:async';

import 'package:chess/chess.dart' as chess;
import 'package:flutter/foundation.dart';

import '../data/local/app_database.dart';
import '../services/chess_engine.dart';

class SessionMove {
  const SessionMove({
    required this.ply,
    required this.san,
    required this.uci,
    required this.fenBefore,
    required this.fenAfter,
    this.classification,
    this.loss,
  });
  final int ply;
  final String san;
  final String uci;
  final String fenBefore;
  final String fenAfter;
  final String? classification;
  final int? loss;
}

class AnalysisSession extends ChangeNotifier {
  AnalysisSession({
    required this.gameId,
    required this.database,
    required this.engine,
  });
  final int gameId;
  final AppDatabase database;
  final ChessEngine engine;

  List<SessionMove> moves = const [];
  List<int> criticalPlies = const [];
  List<EngineLine> engineLines = const [];
  AnalysisBudget budget = AnalysisBudget.normal;
  int currentPly = 0;
  bool flipped = false;
  bool loading = true;
  String? opening;
  String? selectedSquare;
  List<String> legalTargets = const [];
  int? variationBranch;
  final List<SessionMove> variation = [];
  int variationIndex = 0;
  String? motionFrom;
  String? motionTo;
  int motionSerial = 0;
  StreamSubscription<EngineAnalysis>? _analysis;

  String get currentFen {
    if (variationBranch != null && variationIndex > 0) {
      return variation[variationIndex - 1].fenAfter;
    }
    if (currentPly == 0) {
      return moves.isEmpty
          ? chess.Chess.DEFAULT_POSITION
          : moves.first.fenBefore;
    }
    return moves[currentPly - 1].fenAfter;
  }

  SessionMove? get lastMove {
    if (variationBranch != null && variationIndex > 0) {
      return variation[variationIndex - 1];
    }
    return currentPly == 0 ? null : moves[currentPly - 1];
  }

  Future<void> load() async {
    final connection = await database.instance;
    final gameRows = await connection.query(
      'games',
      where: 'id = ?',
      whereArgs: [gameId],
      limit: 1,
    );
    if (gameRows.isEmpty) throw StateError('Game $gameId was not found.');
    opening = gameRows.single['opening'] as String?;
    flipped = gameRows.single['player_color'] == 'black';
    final depthRows = await connection.rawQuery(
      'SELECT MAX(depth) AS depth FROM move_analyses WHERE game_id = ?',
      [gameId],
    );
    final depth = depthRows.single['depth'] as int?;
    final rows = await connection.rawQuery(
      '''
      SELECT m.*, ma.classification, ma.centipawn_loss
      FROM moves m
      LEFT JOIN move_analyses ma ON ma.game_id = m.game_id AND ma.ply = m.ply AND ma.depth = ?
      WHERE m.game_id = ? ORDER BY m.ply
    ''',
      [depth ?? -1, gameId],
    );
    moves = rows
        .map(
          (row) => SessionMove(
            ply: row['ply']! as int,
            san: row['san']! as String,
            uci: row['uci']! as String,
            fenBefore: row['fen_before']! as String,
            fenAfter: row['fen_after']! as String,
            classification: row['classification'] as String?,
            loss: row['centipawn_loss'] as int?,
          ),
        )
        .toList();
    final critical = await connection.query(
      'critical_moments',
      columns: ['ply'],
      where: 'game_id = ?',
      whereArgs: [gameId],
      orderBy: 'ply',
    );
    criticalPlies = critical.map((row) => row['ply']! as int).toList();
    loading = false;
    notifyListeners();
  }

  Future<void> analyzeCurrent() async {
    await _analysis?.cancel();
    await engine.cancel();
    engineLines = const [];
    notifyListeners();
    _analysis = engine
        .analyzePosition(EngineRequest(fen: currentFen, budget: budget))
        .listen((result) {
          if (result.fen != currentFen) return;
          engineLines = result.lines;
          notifyListeners();
        });
  }

  void previous() {
    final reversed = lastMove;
    if (variationBranch != null && variationIndex > 0) {
      variationIndex--;
      if (variationIndex == 0) {
        currentPly = variationBranch!;
        variationBranch = null;
        variation.clear();
      }
    } else if (currentPly > 0) {
      currentPly--;
    }
    _positionChanged(motion: reversed, reverse: true);
  }

  void next() {
    SessionMove? moved;
    if (variationBranch != null && variationIndex < variation.length) {
      variationIndex++;
      moved = variation[variationIndex - 1];
    } else if (currentPly < moves.length) {
      currentPly++;
      moved = moves[currentPly - 1];
    }
    _positionChanged(motion: moved);
  }

  void jumpTo(int ply) {
    currentPly = ply.clamp(0, moves.length);
    variationBranch = null;
    variation.clear();
    variationIndex = 0;
    _positionChanged();
  }

  void flip() {
    flipped = !flipped;
    notifyListeners();
  }

  void setBudget(AnalysisBudget value) {
    budget = value;
    notifyListeners();
    unawaited(analyzeCurrent());
  }

  void selectSquare(String square) {
    final board = chess.Chess.fromFEN(currentFen);
    if (selectedSquare != null && legalTargets.contains(square)) {
      final before = currentFen;
      final from = selectedSquare!;
      board.move({'from': from, 'to': square, 'promotion': 'q'});
      final history = board.getHistory().cast<String>();
      final san = history.last;
      final uci = '$from$square';
      if (variationBranch == null &&
          currentPly < moves.length &&
          moves[currentPly].uci == uci) {
        currentPly++;
      } else {
        variationBranch ??= currentPly;
        if (variationIndex < variation.length) {
          variation.removeRange(variationIndex, variation.length);
        }
        variation.add(
          SessionMove(
            ply: (variationBranch ?? currentPly) + variation.length,
            san: san,
            uci: uci,
            fenBefore: before,
            fenAfter: board.fen,
          ),
        );
        variationIndex = variation.length;
      }
      _positionChanged(motion: lastMove);
      return;
    }
    final targets = board.moves({
      'square': square,
      'verbose': true,
    }).cast<Map<dynamic, dynamic>>();
    selectedSquare = targets.isEmpty ? null : square;
    legalTargets = targets.map((move) => move['to']! as String).toList();
    notifyListeners();
  }

  void _positionChanged({SessionMove? motion, bool reverse = false}) {
    if (motion != null && motion.uci.length >= 4) {
      motionFrom = motion.uci.substring(reverse ? 2 : 0, reverse ? 4 : 2);
      motionTo = motion.uci.substring(reverse ? 0 : 2, reverse ? 2 : 4);
      motionSerial++;
    } else {
      motionFrom = null;
      motionTo = null;
    }
    selectedSquare = null;
    legalTargets = const [];
    notifyListeners();
    unawaited(analyzeCurrent());
  }

  @override
  void dispose() {
    _analysis?.cancel();
    engine.cancel();
    super.dispose();
  }
}
