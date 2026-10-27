import 'dart:math';

import '../services/chess_engine.dart';
import 'move_metrics.dart';

class AnalyzedDecision {
  const AnalyzedDecision({
    required this.ply,
    required this.color,
    required this.san,
    required this.playedUci,
    required this.bestUci,
    required this.fenBefore,
    required this.fenAfter,
    required this.loss,
    required this.classification,
    required this.candidates,
  });
  final int ply;
  final String color;
  final String san;
  final String playedUci;
  final String? bestUci;
  final String fenBefore;
  final String fenAfter;
  final int loss;
  final MoveClassification classification;
  final List<EngineLine> candidates;
}

class CriticalMoment {
  const CriticalMoment({
    required this.decision,
    required this.polarity,
    required this.type,
    required this.score,
    required this.explanation,
  });
  final AnalyzedDecision decision;
  final String polarity;
  final String type;
  final double score;
  final String explanation;
}

List<CriticalMoment> findCriticalMoments(
  List<AnalyzedDecision> decisions,
  String playerColor,
) {
  final ranked = <CriticalMoment>[];
  for (final decision in decisions.where((item) => item.color == playerColor)) {
    if (decision.loss >= 75) {
      final type = decision.loss >= 300
          ? 'Blunder'
          : decision.loss >= 150
          ? 'Mistake'
          : 'Missed Opportunity';
      ranked.add(
        CriticalMoment(
          decision: decision,
          polarity: 'negative',
          type: type,
          score: decision.loss.toDouble(),
          explanation:
              '${(decision.loss / 100).toStringAsFixed(1)} evaluation loss',
        ),
      );
      continue;
    }
    if (decision.playedUci != decision.bestUci ||
        decision.loss > 29 ||
        decision.candidates.length < 2) {
      continue;
    }
    final values = decision.candidates
        .take(2)
        .map((line) => scoreToCp(line.evaluationCp, line.mate))
        .toList();
    if (values.any((value) => value == null)) continue;
    final signedBest = playerColor == 'white' ? values[0]! : -values[0]!;
    final signedSecond = playerColor == 'white' ? values[1]! : -values[1]!;
    final gap = max(0, signedBest - signedSecond);
    if (gap >= 80) {
      final only = gap >= 150;
      ranked.add(
        CriticalMoment(
          decision: decision,
          polarity: 'positive',
          type: only ? 'Only Move' : 'Great Find',
          score: gap * .85,
          explanation: only
              ? 'Only move preserving the position'
              : 'Next-best choice was ${(gap / 100).toStringAsFixed(1)} worse',
        ),
      );
    }
  }
  ranked.sort((a, b) => b.score.compareTo(a.score));
  final selected = <CriticalMoment>[];
  for (final moment in ranked) {
    if (selected.any(
      (item) => (item.decision.ply - moment.decision.ply).abs() <= 2,
    )) {
      continue;
    }
    selected.add(moment);
  }
  selected.sort((a, b) => a.decision.ply.compareTo(b.decision.ply));
  return selected;
}
