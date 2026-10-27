import 'dart:async';

import 'package:flutter/material.dart';

import '../../domain/analysis_session.dart';
import '../../domain/app_controller.dart';
import '../../services/chess_engine.dart';
import '../widgets/chess_board.dart';

class AnalysisWorkspaceScreen extends StatefulWidget {
  const AnalysisWorkspaceScreen({
    required this.gameId,
    required this.controller,
    required this.session,
    this.initialPly = 0,
    super.key,
  });
  final int gameId;
  final AppController controller;
  final AnalysisSession session;
  final int initialPly;

  @override
  State<AnalysisWorkspaceScreen> createState() =>
      _AnalysisWorkspaceScreenState();
}

class _AnalysisWorkspaceScreenState extends State<AnalysisWorkspaceScreen> {
  AnalysisSession get session => widget.session;
  bool _showSuggestions = true;

  @override
  void initState() {
    super.initState();
    session.addListener(_refresh);
    unawaited(_prepare());
  }

  Future<void> _prepare() async {
    await session.load();
    await widget.controller.analyzeGame(widget.gameId);
    await session.load();
    if (widget.initialPly > 0) {
      session.jumpTo(widget.initialPly);
    }
    await session.analyzeCurrent();
  }

  void _refresh() {
    if (mounted) setState(() {});
  }

  @override
  void dispose() {
    session.removeListener(_refresh);
    session.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    body: SafeArea(
      child: Column(
        children: [
          _header(context),
          _engineLines(),
          _evaluationBar(),
          ChessBoard(
            session: session,
            suggestionUci: _showSuggestions
                ? session.engineLines.firstOrNull?.bestMoveUci
                : null,
          ),
          _opening(),
          Expanded(child: _notation()),
          if (session.criticalPlies.isNotEmpty) _criticalNavigation(),
          _controls(),
        ],
      ),
    ),
  );

  Widget _header(BuildContext context) => SizedBox(
    height: 44,
    child: Stack(
      alignment: Alignment.center,
      children: [
        const Text(
          'Analysis',
          style: TextStyle(fontWeight: FontWeight.w800, fontSize: 17),
        ),
        Align(
          alignment: Alignment.centerLeft,
          child: IconButton(
            onPressed: () => Navigator.pop(context),
            tooltip: 'Back',
            icon: const Icon(Icons.arrow_back),
          ),
        ),
        Align(
          alignment: Alignment.centerRight,
          child: IconButton(
            onPressed: _settings,
            tooltip: 'Analysis settings',
            icon: const Icon(Icons.settings_outlined),
          ),
        ),
      ],
    ),
  );

  Widget _engineLines() => SizedBox(
    height: 58,
    child: session.engineLines.isEmpty
        ? const Center(
            child: Text('Analyzing…', style: TextStyle(fontSize: 12)),
          )
        : Column(
            children: session.engineLines
                .take(2)
                .map(
                  (line) => InkWell(
                    onTap: () => _playUci(line.bestMoveUci),
                    child: SizedBox(
                      height: 28,
                      child: Row(
                        children: [
                          SizedBox(
                            width: 58,
                            child: Text(
                              _evaluation(line),
                              textAlign: TextAlign.right,
                              style: const TextStyle(
                                fontWeight: FontWeight.w800,
                              ),
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Text(
                              line.pv.take(5).join(' '),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(fontSize: 12),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                )
                .toList(),
          ),
  );

  Widget _evaluationBar() {
    final line = session.engineLines.firstOrNull;
    final cp = line?.evaluationCp ?? 0;
    final white = line?.mate != null
        ? (line!.mate! > 0 ? .96 : .04)
        : (.5 + cp.clamp(-1000, 1000) / 2500).clamp(.04, .96);
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 2),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(2),
        child: SizedBox(
          height: 8,
          child: Row(
            children: [
              Expanded(
                flex: (white * 1000).round(),
                child: const ColoredBox(color: Color(0xfff3f3eb)),
              ),
              Expanded(
                flex: ((1 - white) * 1000).round(),
                child: const ColoredBox(color: Color(0xff292a27)),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _opening() => Container(
    width: double.infinity,
    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
    child: Text(
      session.opening ?? 'Opening not identified',
      maxLines: 1,
      overflow: TextOverflow.ellipsis,
      style: const TextStyle(fontWeight: FontWeight.w700),
    ),
  );

  Widget _notation() => SingleChildScrollView(
    padding: const EdgeInsets.fromLTRB(12, 2, 12, 8),
    child: Wrap(
      spacing: 6,
      runSpacing: 5,
      children: [
        for (final move in session.moves)
          InkWell(
            onTap: () => session.jumpTo(move.ply),
            child: Text(
              '${move.ply.isOdd ? '${(move.ply + 1) ~/ 2}.' : ''}${move.san}',
              style: TextStyle(
                fontWeight: move.ply == session.currentPly
                    ? FontWeight.w900
                    : FontWeight.w500,
                color: move.ply <= session.currentPly
                    ? null
                    : Theme.of(context).colorScheme.onSurfaceVariant,
              ),
            ),
          ),
        if (session.variation.isNotEmpty)
          Text(
            '(${session.variation.map((move) => move.san).join(' ')})',
            style: TextStyle(
              color: Theme.of(context).colorScheme.primary,
              fontStyle: FontStyle.italic,
            ),
          ),
      ],
    ),
  );

  Widget _criticalNavigation() {
    final currentIndex = session.criticalPlies.lastIndexWhere(
      (ply) => ply <= session.currentPly,
    );
    return SizedBox(
      height: 34,
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Text(
            'Critical',
            style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700),
          ),
          const SizedBox(width: 8),
          Text(
            '${currentIndex < 0 ? 0 : currentIndex + 1} / ${session.criticalPlies.length}',
            style: const TextStyle(fontSize: 12),
          ),
          IconButton(
            onPressed: currentIndex > 0
                ? () => session.jumpTo(session.criticalPlies[currentIndex - 1])
                : null,
            visualDensity: VisualDensity.compact,
            icon: const Icon(Icons.chevron_left),
          ),
          IconButton(
            onPressed: currentIndex + 1 < session.criticalPlies.length
                ? () => session.jumpTo(session.criticalPlies[currentIndex + 1])
                : null,
            visualDensity: VisualDensity.compact,
            icon: const Icon(Icons.chevron_right),
          ),
        ],
      ),
    );
  }

  Widget _controls() => SafeArea(
    top: false,
    child: SizedBox(
      height: 58,
      child: Row(
        children: [
          Expanded(
            child: IconButton(
              onPressed: () {},
              tooltip: 'Menu',
              icon: const Icon(Icons.menu, size: 28),
            ),
          ),
          Expanded(
            child: IconButton(
              onPressed: session.flip,
              tooltip: 'Flip board',
              icon: const Icon(Icons.swap_vert, size: 28),
            ),
          ),
          Expanded(
            child: IconButton(
              onPressed: session.currentPly > 0 ? session.previous : null,
              tooltip: 'Previous move',
              icon: const Icon(Icons.chevron_left, size: 38),
            ),
          ),
          Expanded(
            child: IconButton(
              onPressed: session.currentPly < session.moves.length
                  ? session.next
                  : null,
              tooltip: 'Next move',
              icon: const Icon(Icons.chevron_right, size: 38),
            ),
          ),
        ],
      ),
    ),
  );

  void _playUci(String? uci) {
    if (uci == null || uci.length < 4) return;
    session.selectSquare(uci.substring(0, 2));
    session.selectSquare(uci.substring(2, 4));
  }

  String _evaluation(EngineLine line) => line.mate != null
      ? 'M${line.mate}'
      : ((line.evaluationCp ?? 0) / 100).toStringAsFixed(2);
  Future<void> _settings() async {
    await showModalBottomSheet<void>(
      context: context,
      builder: (context) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text(
                'Analysis Settings',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800),
              ),
              SwitchListTile(
                title: const Text('Suggestion arrows'),
                value: _showSuggestions,
                onChanged: (value) {
                  setState(() => _showSuggestions = value);
                  Navigator.pop(context);
                },
              ),
              const Align(
                alignment: Alignment.centerLeft,
                child: Padding(
                  padding: EdgeInsets.only(left: 16, top: 8),
                  child: Text('Engine strength'),
                ),
              ),
              SegmentedButton<AnalysisBudget>(
                segments: const [
                  ButtonSegment(
                    value: AnalysisBudget.fast,
                    label: Text('Fast'),
                  ),
                  ButtonSegment(
                    value: AnalysisBudget.normal,
                    label: Text('Normal'),
                  ),
                  ButtonSegment(
                    value: AnalysisBudget.deep,
                    label: Text('Deep'),
                  ),
                ],
                selected: {session.budget},
                onSelectionChanged: (value) => session.setBudget(value.first),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
