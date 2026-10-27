import 'dart:async';

import 'package:chess/chess.dart' as chess;
import 'package:chess_analytics_mobile/data/local/app_database.dart';
import 'package:chess_analytics_mobile/data/repositories/engine_cache_repository.dart';
import 'package:chess_analytics_mobile/services/chess_engine.dart';
import 'package:chess_analytics_mobile/services/local_stockfish_engine.dart';
import 'package:chess_analytics_mobile/services/stockfish_transport.dart';
import 'package:chess_analytics_mobile/services/uci_parser.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

class FakeUciTransport implements UciTransport {
  final controller = StreamController<String>.broadcast();
  final commands = <String>[];
  bool autoRespond = true;

  @override
  Stream<String> get output => controller.stream;
  @override
  Future<void> start() async {}
  @override
  void send(String command) {
    commands.add(command);
    if (command == 'stop') {
      scheduleMicrotask(() => controller.add('bestmove 0000'));
    } else if (command.startsWith('go depth ') && autoRespond) {
      final depth = int.parse(command.split(' ').last);
      scheduleMicrotask(() {
        controller.add(
          'info depth $depth multipv 1 score cp 24 nodes 100 pv e2e4 e7e5',
        );
        controller.add(
          'info depth $depth multipv 2 score cp 16 nodes 90 pv d2d4 d7d5',
        );
        controller.add('bestmove e2e4');
      });
    }
  }

  @override
  Future<void> dispose() => controller.close();
}

void main() {
  sqfliteFfiInit();

  test('UCI parser handles centipawn and mate MultiPV lines', () {
    const parser = UciInfoParser();
    final cp = parser.parse(
      'info depth 12 multipv 2 score cp -31 nodes 42 pv c7c5 g1f3',
    );
    final mate = parser.parse('info depth 18 score mate 3 pv h5f7 e8f7');
    expect(cp?.rank, 2);
    expect(cp?.evaluationCp, -31);
    expect(cp?.pv.first, 'c7c5');
    expect(mate?.mate, 3);
  });

  test('analysis emits shallow result, refines, then reuses cache', () async {
    final database = AppDatabase(
      factory: databaseFactoryFfi,
      databasePath: inMemoryDatabasePath,
    );
    final transport = FakeUciTransport();
    final engine = LocalStockfishEngine(
      transport: transport,
      cache: EngineCacheRepository(database),
    );
    final request = EngineRequest(
      fen: chess.Chess.DEFAULT_POSITION,
      budget: AnalysisBudget.fast,
    );

    final results = await engine.analyzePosition(request).toList();
    expect(results.map((result) => result.depth), [6, 10]);
    expect(results.last.isFinal, isTrue);
    expect(results.last.lines, hasLength(2));

    transport.commands.clear();
    final cached = await engine.analyzePosition(request).toList();
    expect(cached, hasLength(1));
    expect(cached.single.fromCache, isTrue);
    expect(cached.single.isFinal, isTrue);
    expect(
      transport.commands.where((command) => command.startsWith('go ')),
      isEmpty,
    );
    await engine.dispose();
    await database.close();
  });

  test('cancel stops active search and closes the abandoned stream', () async {
    final database = AppDatabase(
      factory: databaseFactoryFfi,
      databasePath: inMemoryDatabasePath,
    );
    final transport = FakeUciTransport()..autoRespond = false;
    final engine = LocalStockfishEngine(
      transport: transport,
      cache: EngineCacheRepository(database),
    );
    final done = engine
        .analyzePosition(
          EngineRequest(
            fen: chess.Chess.DEFAULT_POSITION,
            budget: AnalysisBudget.deep,
          ),
        )
        .drain<void>();
    await Future<void>.delayed(const Duration(milliseconds: 10));
    await engine.cancel();
    await done.timeout(const Duration(seconds: 1));
    expect(transport.commands, contains('stop'));
    await engine.dispose();
    await database.close();
  });

  test('engine scores are normalized to White perspective', () async {
    final database = AppDatabase(
      factory: databaseFactoryFfi,
      databasePath: inMemoryDatabasePath,
    );
    final engine = LocalStockfishEngine(
      transport: FakeUciTransport(),
      cache: EngineCacheRepository(database),
    );
    final blackToMove = chess.Chess.DEFAULT_POSITION.replaceFirst(' w ', ' b ');
    final result = await engine
        .analyzePosition(
          EngineRequest(fen: blackToMove, budget: AnalysisBudget.fast),
        )
        .last;
    expect(result.lines.first.evaluationCp, -24);
    await engine.dispose();
    await database.close();
  });
}
