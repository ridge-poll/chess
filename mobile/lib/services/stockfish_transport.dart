import 'package:multistockfish/multistockfish.dart';

abstract interface class UciTransport {
  Stream<String> get output;
  Future<void> start();
  void send(String command);
  Future<void> dispose();
}

class NativeStockfishTransport implements UciTransport {
  Stockfish? _engine;
  @override
  Stream<String> get output {
    if (_engine == null) throw StateError('Stockfish has not started.');
    return _engine!.stdout;
  }

  @override
  Future<void> start() async =>
      _engine ??= await Stockfish.create(flavor: StockfishFlavor.light);
  @override
  void send(String command) {
    if (_engine == null) throw StateError('Stockfish has not started.');
    _engine!.stdin = command;
  }

  @override
  Future<void> dispose() async {
    final engine = _engine;
    _engine = null;
    await engine?.dispose();
  }
}
