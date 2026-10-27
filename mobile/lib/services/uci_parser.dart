import 'chess_engine.dart';

class UciInfoParser {
  const UciInfoParser();
  EngineLine? parse(String input) {
    if (!input.startsWith('info ') || !input.contains(' pv ')) return null;
    final tokens = input.trim().split(RegExp(r'\s+'));
    final depth = _after(tokens, 'depth');
    final scoreIndex = tokens.indexOf('score');
    final pvIndex = tokens.indexOf('pv');
    if (depth == null ||
        scoreIndex < 0 ||
        pvIndex < 0 ||
        pvIndex + 1 >= tokens.length) {
      return null;
    }
    int? cp;
    int? mate;
    if (tokens.length > scoreIndex + 2) {
      final value = int.tryParse(tokens[scoreIndex + 2]);
      if (tokens[scoreIndex + 1] == 'cp') cp = value;
      if (tokens[scoreIndex + 1] == 'mate') mate = value;
    }
    if (cp == null && mate == null) return null;
    return EngineLine(
      rank: _after(tokens, 'multipv') ?? 1,
      depth: depth,
      evaluationCp: cp,
      mate: mate,
      pv: tokens.sublist(pvIndex + 1),
    );
  }

  int? _after(List<String> tokens, String key) {
    final index = tokens.indexOf(key);
    return index >= 0 && index + 1 < tokens.length
        ? int.tryParse(tokens[index + 1])
        : null;
  }
}
