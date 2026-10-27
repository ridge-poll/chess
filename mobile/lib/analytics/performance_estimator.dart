import 'dart:math';

const performanceEstimatorVersion = 'heuristic-v2';

class PerformanceEstimate {
  const PerformanceEstimate({
    required this.rating,
    required this.confidence,
    required this.sampleQuality,
    required this.version,
  });
  final int? rating;
  final double confidence;
  final String sampleQuality;
  final String version;
}

PerformanceEstimate estimatePerformance({
  required List<int> losses,
  required String timeClass,
  int? ownRating,
  int? opponentRating,
}) {
  final clean = losses.map((loss) => loss.clamp(0, 1000)).toList();
  final count = clean.length;
  final confidence = ((count - 4) / 20).clamp(0, 1).toDouble();
  final quality = count < 8
      ? 'insufficient'
      : confidence < .55
      ? 'low'
      : 'moderate';
  if (count < 8) {
    return PerformanceEstimate(
      rating: null,
      confidence: confidence,
      sampleQuality: quality,
      version: performanceEstimatorVersion,
    );
  }
  clean.sort();
  final average = clean.reduce((a, b) => a + b) / count;
  final median = count.isOdd
      ? clean[count ~/ 2].toDouble()
      : (clean[count ~/ 2 - 1] + clean[count ~/ 2]) / 2;
  final severe = clean.where((loss) => loss >= 150).length / count;
  final blunders = clean.where((loss) => loss >= 300).length / count;
  final cleanRate = clean.where((loss) => loss <= 30).length / count;
  final behavior =
      2200 -
      78 * sqrt(average) -
      2.2 * median -
      500 * severe -
      450 * blunders +
      100 * cleanRate;
  final ratings = [ownRating, opponentRating].whereType<int>();
  final context = ratings.isEmpty
      ? behavior
      : ratings.reduce((a, b) => a + b) / ratings.length;
  final adjustment =
      {
        'Bullet': -120,
        'Blitz': -55,
        'Rapid': 0,
        'Classical': 35,
        'Daily': 45,
      }[timeClass] ??
      0;
  final estimate = (behavior * .76 + context * .24 + adjustment).clamp(
    400,
    2800,
  );
  return PerformanceEstimate(
    rating: (estimate / 50).round() * 50,
    confidence: confidence,
    sampleQuality: quality,
    version: performanceEstimatorVersion,
  );
}
