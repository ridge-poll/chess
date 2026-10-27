class EngineRequest {
  const EngineRequest({
    required this.fen,
    required this.budget,
    this.multiPv = 2,
  });
  final String fen;
  final AnalysisBudget budget;
  final int multiPv;
  int get targetDepth => switch (budget) {
    AnalysisBudget.fast => 10,
    AnalysisBudget.normal => 16,
    AnalysisBudget.deep => 22,
  };
}

enum AnalysisBudget { fast, normal, deep }

class EngineLine {
  const EngineLine({
    required this.rank,
    required this.depth,
    required this.pv,
    this.evaluationCp,
    this.mate,
  });
  final int rank;
  final int depth;
  final int? evaluationCp;
  final int? mate;
  final List<String> pv;
  String? get bestMoveUci => pv.isEmpty ? null : pv.first;
}

class EngineAnalysis {
  const EngineAnalysis({
    required this.fen,
    required this.depth,
    required this.lines,
    required this.isFinal,
    this.fromCache = false,
  });
  final String fen;
  final int depth;
  final List<EngineLine> lines;
  final bool isFinal;
  final bool fromCache;
}

abstract interface class ChessEngine {
  Stream<EngineAnalysis> analyzePosition(EngineRequest request);
  Future<void> cancel();
  Future<void> dispose();
}
