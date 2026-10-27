const maxStatisticalCpl = 1000;
const mateScore = 10000;

enum MoveClassification { best, great, good, inaccuracy, mistake, blunder }

int? scoreToCp(int? scoreCp, int? mate) {
  if (scoreCp != null) return scoreCp;
  if (mate == null) return null;
  final sign = mate > 0 ? 1 : -1;
  return sign * (mateScore - mate.abs().clamp(0, 100) * 100);
}

int? moveLoss({
  required int? beforeCp,
  required int? afterCp,
  required int? mateBefore,
  required int? mateAfter,
  required String color,
  bool isCheckmateAfter = false,
}) {
  if (isCheckmateAfter) return 0;
  final before = scoreToCp(beforeCp, mateBefore);
  final after = scoreToCp(afterCp, mateAfter);
  if (before == null || after == null) return null;
  final raw = color == 'white' ? before - after : after - before;
  return raw.clamp(0, maxStatisticalCpl);
}

MoveClassification classifyMove(int loss, String? playedUci, String? bestUci) {
  if (playedUci != null && bestUci != null && playedUci == bestUci) {
    return MoveClassification.best;
  }
  if (loss > 299) return MoveClassification.blunder;
  if (loss > 149) return MoveClassification.mistake;
  if (loss > 74) return MoveClassification.inaccuracy;
  if (loss > 29) return MoveClassification.good;
  return MoveClassification.great;
}

double? accuracyFromAcpl(double? acpl) =>
    acpl == null ? null : (100 - acpl / 3).clamp(0, 100).toDouble();
