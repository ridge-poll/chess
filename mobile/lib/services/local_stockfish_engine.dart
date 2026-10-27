import 'dart:async';

import '../data/repositories/engine_cache_repository.dart';
import 'chess_engine.dart';
import 'stockfish_transport.dart';
import 'uci_parser.dart';

class LocalStockfishEngine implements ChessEngine {
  LocalStockfishEngine({
    required this.transport,
    required this.cache,
    this.parser = const UciInfoParser(),
  });

  final UciTransport transport;
  final EngineCacheRepository cache;
  final UciInfoParser parser;
  int _generation = 0;
  bool _started = false;
  bool _searching = false;

  @override
  Stream<EngineAnalysis> analyzePosition(EngineRequest request) async* {
    final generation = ++_generation;
    if (_searching) transport.send('stop');
    final cached = await cache.strongest(request.fen, request.multiPv);
    if (generation != _generation) return;
    if (cached != null) {
      yield EngineAnalysis(
        fen: cached.fen,
        depth: cached.depth,
        lines: cached.lines,
        isFinal: cached.depth >= request.targetDepth,
        fromCache: true,
      );
      if (cached.depth >= request.targetDepth) return;
    }
    if (!_started) {
      await transport.start();
      _started = true;
    }
    transport.send(
      'setoption name MultiPV value ${request.multiPv.clamp(1, 5)}',
    );
    transport.send('position fen ${request.fen}');
    final completedDepth = cached?.depth ?? 0;
    final stages = <int>{
      6,
      10,
      request.targetDepth,
    }.where((depth) => depth > completedDepth).toList()..sort();
    for (final depth in stages) {
      if (generation != _generation) return;
      final result = await _analyzeDepth(
        request.fen,
        depth,
        request.multiPv,
        generation,
      );
      if (result == null || generation != _generation) return;
      final finalResult = EngineAnalysis(
        fen: result.fen,
        depth: result.depth,
        lines: result.lines,
        isFinal: depth == request.targetDepth,
      );
      await cache.store(finalResult);
      if (generation != _generation) return;
      yield finalResult;
    }
  }

  Future<EngineAnalysis?> _analyzeDepth(
    String fen,
    int depth,
    int multiPv,
    int generation,
  ) async {
    final completion = Completer<EngineAnalysis?>();
    final lines = <int, EngineLine>{};
    late final StreamSubscription<String> subscription;
    subscription = transport.output.listen(
      (output) {
        if (output.startsWith('bestmove')) {
          if (!completion.isCompleted) {
            if (generation != _generation) {
              completion.complete(null);
              return;
            }
            final ordered = lines.values.toList()
              ..sort((a, b) => a.rank.compareTo(b.rank));
            final whitePerspective = fen.split(' ')[1] == 'b'
                ? ordered.map(_invertScore).toList()
                : ordered;
            completion.complete(
              whitePerspective.isEmpty
                  ? null
                  : EngineAnalysis(
                      fen: fen,
                      depth: depth,
                      lines: whitePerspective.take(multiPv).toList(),
                      isFinal: false,
                    ),
            );
          }
          return;
        }
        if (generation != _generation) return;
        final line = parser.parse(output);
        if (line != null && line.depth <= depth) lines[line.rank] = line;
      },
      onError: (Object error, StackTrace stack) {
        if (!completion.isCompleted) completion.completeError(error, stack);
      },
    );
    _searching = true;
    transport.send('go depth $depth');
    try {
      return await completion.future.timeout(const Duration(seconds: 45));
    } finally {
      _searching = false;
      await subscription.cancel();
    }
  }

  EngineLine _invertScore(EngineLine line) => EngineLine(
    rank: line.rank,
    depth: line.depth,
    evaluationCp: line.evaluationCp == null ? null : -line.evaluationCp!,
    mate: line.mate == null ? null : -line.mate!,
    pv: line.pv,
  );

  @override
  Future<void> cancel() async {
    _generation++;
    if (_searching) transport.send('stop');
  }

  @override
  Future<void> dispose() async {
    await cancel();
    await transport.dispose();
    _started = false;
  }
}
