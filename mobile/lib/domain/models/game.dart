enum GameResult { win, loss, draw, unknown }

class GameSummary {
  const GameSummary({
    required this.id,
    required this.profileId,
    required this.white,
    required this.black,
    required this.playedAt,
    required this.result,
    required this.playerColor,
    required this.timeClass,
    required this.pgn,
    this.whiteElo,
    this.blackElo,
    this.opening,
    this.accuracy,
  });
  final int id;
  final int profileId;
  final String white;
  final String black;
  final DateTime playedAt;
  final String result;
  final String playerColor;
  final String timeClass;
  final String pgn;
  final int? whiteElo;
  final int? blackElo;
  final String? opening;
  final double? accuracy;

  String get opponent => playerColor == 'black' ? white : black;
  int? get opponentElo => playerColor == 'black' ? whiteElo : blackElo;
  GameResult get userResult {
    if (result == '1/2-1/2') return GameResult.draw;
    if ((result == '1-0' && playerColor == 'white') ||
        (result == '0-1' && playerColor == 'black')) {
      return GameResult.win;
    }
    if (result == '1-0' || result == '0-1') return GameResult.loss;
    return GameResult.unknown;
  }

  factory GameSummary.fromMap(Map<String, Object?> map) => GameSummary(
    id: map['id']! as int,
    profileId: map['profile_id']! as int,
    white: map['white']! as String,
    black: map['black']! as String,
    playedAt: DateTime.parse(map['played_at']! as String),
    result: map['result']! as String,
    playerColor: map['player_color']! as String,
    timeClass: map['time_class']! as String,
    pgn: map['pgn']! as String,
    whiteElo: map['white_elo'] as int?,
    blackElo: map['black_elo'] as int?,
    opening: map['opening'] as String?,
    accuracy: (map['accuracy'] as num?)?.toDouble(),
  );
}
