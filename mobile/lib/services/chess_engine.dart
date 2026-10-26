class EngineRequest {
  const EngineRequest({
    required this.fen,
    required this.budget,
    this.multiPv = 2,
  });
  final String fen;
  final AnalysisBudget budget;
  final int multiPv;
}

enum AnalysisBudget { fast, normal, deep }

abstract interface class ChessEngine {
  Stream<Object> analyzePosition(EngineRequest request);
  Future<void> cancel();
}

class StockfishUnavailable implements ChessEngine {
  @override
  Stream<Object> analyzePosition(EngineRequest request) => Stream.error(
    UnsupportedError('Local Stockfish arrives in checkpoint 3.'),
  );

  @override
  Future<void> cancel() async {}
}
