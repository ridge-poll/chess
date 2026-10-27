import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../analytics/move_metrics.dart';
import '../../domain/app_controller.dart';
import '../../domain/game_diagnostics.dart';
import 'analysis_workspace_screen.dart';

class GameDetailScreen extends StatefulWidget {
  const GameDetailScreen({
    required this.gameId,
    required this.controller,
    super.key,
  });
  final int gameId;
  final AppController controller;

  @override
  State<GameDetailScreen> createState() => _GameDetailScreenState();
}

class _GameDetailScreenState extends State<GameDetailScreen> {
  GameDiagnostics? report;
  Object? error;
  bool analyzing = false;

  GameDiagnosticsRepository get repository =>
      GameDiagnosticsRepository(widget.controller.gameAnalyzer!.database);

  @override
  void initState() {
    super.initState();
    unawaited(_load());
  }

  Future<void> _load() async {
    try {
      final initial = await repository.load(widget.gameId);
      if (mounted) setState(() => report = initial);
      final incomplete = initial.moves.any(
        (move) => move.classification == null,
      );
      if (incomplete) {
        setState(() => analyzing = true);
        await widget.controller.analyzeGame(widget.gameId);
        final updated = await repository.load(widget.gameId);
        if (mounted) setState(() => report = updated);
      }
    } catch (value) {
      if (mounted) setState(() => error = value);
    } finally {
      if (mounted) setState(() => analyzing = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Game Review'),
      centerTitle: true,
      actions: [
        IconButton(
          onPressed: report == null ? null : () => _openAnalysis(0),
          tooltip: 'Analyze game',
          icon: const Icon(Icons.analytics_outlined),
        ),
      ],
    ),
    body: switch ((report, error)) {
      (_, final failure?) => Center(
        child: Text('Could not load game: $failure'),
      ),
      (null, _) => const Center(child: CircularProgressIndicator.adaptive()),
      (final data?, _) => _content(data),
    },
  );

  Widget _content(GameDiagnostics data) => ListView(
    padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
    children: [
      _GameHeader(data: data),
      if (analyzing) ...[
        const SizedBox(height: 12),
        const LinearProgressIndicator(minHeight: 2),
        const SizedBox(height: 5),
        const Text('Analyzing game locally…', style: TextStyle(fontSize: 12)),
      ],
      const SizedBox(height: 22),
      _sectionTitle('Evaluation'),
      _TrajectoryChart(
        values: data.moves
            .map((move) => move.evaluationCp?.toDouble())
            .toList(),
        baseline: 0,
        positiveColor: const Color(0xff769656),
        negativeColor: const Color(0xffd85040),
      ),
      const SizedBox(height: 22),
      _sectionTitle('Move Quality'),
      _QualitySummary(counts: data.qualityCounts),
      if (data.criticalMoments.isNotEmpty) ...[
        const SizedBox(height: 22),
        _sectionTitle('Critical Moments'),
        ...data.criticalMoments.map(
          (moment) => _CriticalRow(
            moment: moment,
            onTap: () => _openAnalysis(moment.ply),
          ),
        ),
      ],
      if (data.estimatedUser != null || data.estimatedOpponent != null) ...[
        const SizedBox(height: 22),
        _sectionTitle('Estimated Performance'),
        _Performance(data: data),
      ],
      const SizedBox(height: 22),
      _sectionTitle('Game Shape'),
      _LabeledTrajectory(
        label: 'Volatility',
        values: _volatility(data.moves),
        low: 'quiet',
        high: 'sharp',
        color: const Color(0xffdd8b2c),
      ),
      const SizedBox(height: 14),
      _LabeledTrajectory(
        label: 'Position structure',
        values: data.moves.map((move) => move.openness).toList(),
        low: 'closed',
        high: 'open',
        color: const Color(0xff4f87b8),
      ),
      const SizedBox(height: 22),
      _sectionTitle('Your Phases'),
      _PhaseSummary(phases: data.phases),
      if (data.moves.any((move) => move.timeSpentMs != null)) ...[
        const SizedBox(height: 22),
        _sectionTitle('Time Per Move'),
        _TimePlot(moves: data.moves, userColor: data.playerColor),
      ],
      const SizedBox(height: 22),
      _sectionTitle('Moves'),
      _MoveRecord(moves: data.moves, onTap: _openAnalysis),
      const SizedBox(height: 28),
      OutlinedButton.icon(
        onPressed: () => _delete(data),
        style: OutlinedButton.styleFrom(
          foregroundColor: Theme.of(context).colorScheme.error,
          side: BorderSide(color: Theme.of(context).colorScheme.error),
        ),
        icon: const Icon(Icons.delete_outline),
        label: const Text('Delete Game'),
      ),
    ],
  );

  Widget _sectionTitle(String value) => Padding(
    padding: const EdgeInsets.only(bottom: 9),
    child: Text(
      value.toUpperCase(),
      style: const TextStyle(
        fontSize: 11,
        fontWeight: FontWeight.w800,
        letterSpacing: 1.1,
      ),
    ),
  );

  Future<void> _openAnalysis(int ply) => Navigator.of(context).push(
    MaterialPageRoute<void>(
      builder: (_) => AnalysisWorkspaceScreen(
        gameId: widget.gameId,
        initialPly: ply,
        controller: widget.controller,
        session: widget.controller.createAnalysisSession(widget.gameId),
      ),
    ),
  );

  Future<void> _delete(GameDiagnostics data) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete game?'),
        content: Text(
          '${data.userName} vs ${data.opponentName} and its analysis will be removed.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    await widget.controller.deleteGame(widget.gameId);
    if (mounted) Navigator.pop(context);
  }
}

class _GameHeader extends StatelessWidget {
  const _GameHeader({required this.data});
  final GameDiagnostics data;

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(
        '${data.userName}${_elo(data.userElo)}  —  ${data.opponentName}${_elo(data.opponentElo)}',
        style: Theme.of(context).textTheme.titleLarge
            ?.copyWith(fontWeight: FontWeight.w800),
      ),
      const SizedBox(height: 4),
      Text(
        '${data.result} · ${data.timeClass}${data.timeControl == null ? '' : ' · ${data.timeControl}'}',
        style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant),
      ),
      if (data.opening != null) ...[
        const SizedBox(height: 4),
        Text(
          data.opening!,
          style: const TextStyle(fontWeight: FontWeight.w600),
        ),
      ],
    ],
  );

  String _elo(int? value) => value == null ? '' : ' ($value)';
}

class _QualitySummary extends StatelessWidget {
  const _QualitySummary({required this.counts});
  final Map<MoveClassification, int> counts;

  @override
  Widget build(BuildContext context) => Column(
    children: MoveClassification.values.map((item) {
      final count = counts[item] ?? 0;
      final maxCount = counts.values.fold(1, math.max);
      return SizedBox(
        height: 27,
        child: Row(
          children: [
            SizedBox(
              width: 82,
              child: Text(_label(item), style: const TextStyle(fontSize: 12)),
            ),
            Expanded(
              child: Align(
                alignment: Alignment.centerLeft,
                child: FractionallySizedBox(
                  widthFactor: count / maxCount,
                  child: Container(
                    height: 6,
                    decoration: BoxDecoration(
                      color: qualityColor(item),
                      borderRadius: BorderRadius.circular(3),
                    ),
                  ),
                ),
              ),
            ),
            SizedBox(
              width: 28,
              child: Text(
                '$count',
                textAlign: TextAlign.right,
                style: const TextStyle(fontWeight: FontWeight.w700),
              ),
            ),
          ],
        ),
      );
    }).toList(),
  );
}

class _CriticalRow extends StatelessWidget {
  const _CriticalRow({required this.moment, required this.onTap});
  final CriticalDiagnostic moment;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final positive = moment.polarity == 'positive';
    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 10),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: 4,
              height: 42,
              color: positive
                  ? const Color(0xff769656)
                  : const Color(0xffd85040),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '${_moveLabel(moment.ply)} ${moment.san}  ${_title(moment.type)}',
                    style: const TextStyle(fontWeight: FontWeight.w800),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    moment.explanation,
                    style: TextStyle(
                      fontSize: 12,
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
              ),
            ),
            const Icon(Icons.chevron_right, size: 20),
          ],
        ),
      ),
    );
  }
}

class _Performance extends StatelessWidget {
  const _Performance({required this.data});
  final GameDiagnostics data;

  @override
  Widget build(BuildContext context) => Row(
    children: [
      Expanded(child: _value('You', data.estimatedUser)),
      Container(width: 1, height: 36, color: Theme.of(context).dividerColor),
      Expanded(child: _value('Opponent', data.estimatedOpponent)),
    ],
  );

  Widget _value(String label, int? rating) => Column(
    children: [
      Text(label, style: const TextStyle(fontSize: 12)),
      Text(
        rating == null ? 'Not enough data' : '~$rating',
        style: const TextStyle(fontSize: 19, fontWeight: FontWeight.w800),
      ),
    ],
  );
}

class _LabeledTrajectory extends StatelessWidget {
  const _LabeledTrajectory({
    required this.label,
    required this.values,
    required this.low,
    required this.high,
    required this.color,
  });
  final String label;
  final List<double> values;
  final String low;
  final String high;
  final Color color;

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Row(
        children: [
          Text(label, style: const TextStyle(fontWeight: FontWeight.w700)),
          const Spacer(),
          Text('$low  →  $high', style: const TextStyle(fontSize: 11)),
        ],
      ),
      SizedBox(
        height: 55,
        child: CustomPaint(
          painter: _LinePainter(values: values, color: color, baseline: null),
          size: Size.infinite,
        ),
      ),
    ],
  );
}

class _TrajectoryChart extends StatelessWidget {
  const _TrajectoryChart({
    required this.values,
    required this.baseline,
    required this.positiveColor,
    required this.negativeColor,
  });
  final List<double?> values;
  final double baseline;
  final Color positiveColor;
  final Color negativeColor;

  @override
  Widget build(BuildContext context) => SizedBox(
    height: 150,
    child: CustomPaint(
      painter: _EvalPainter(
        values: values,
        positive: positiveColor,
        negative: negativeColor,
        grid: Theme.of(context).dividerColor,
      ),
      size: Size.infinite,
    ),
  );
}

class _PhaseSummary extends StatelessWidget {
  const _PhaseSummary({required this.phases});
  final List<PhaseDiagnostic> phases;

  @override
  Widget build(BuildContext context) => Row(
    children: phases
        .map(
          (phase) => Expanded(
            child: Column(
              children: [
                Text(phase.name, style: const TextStyle(fontSize: 12)),
                const SizedBox(height: 3),
                Text(
                  phase.averageLoss == null
                      ? '—'
                      : '${phase.averageLoss!.round()} CPL',
                  style: const TextStyle(fontWeight: FontWeight.w800),
                ),
                Text(
                  '${phase.moveCount} moves',
                  style: TextStyle(
                    fontSize: 10,
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
              ],
            ),
          ),
        )
        .toList(),
  );
}

class _TimePlot extends StatelessWidget {
  const _TimePlot({required this.moves, required this.userColor});
  final List<DiagnosticMove> moves;
  final String userColor;

  @override
  Widget build(BuildContext context) => SizedBox(
    height: 100,
    child: CustomPaint(
      painter: _StemPainter(
        moves: moves,
        userColor: userColor,
        accent: Theme.of(context).colorScheme.primary,
        dark: Theme.of(context).brightness == Brightness.dark,
      ),
      size: Size.infinite,
    ),
  );
}

class _MoveRecord extends StatelessWidget {
  const _MoveRecord({required this.moves, required this.onTap});
  final List<DiagnosticMove> moves;
  final ValueChanged<int> onTap;

  @override
  Widget build(BuildContext context) {
    final rows = (moves.length / 2).ceil();
    return Column(
      children: List.generate(rows, (index) {
        final white = moves[index * 2];
        final black = index * 2 + 1 < moves.length
            ? moves[index * 2 + 1]
            : null;
        return Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            SizedBox(
              width: 28,
              child: Padding(
                padding: const EdgeInsets.only(top: 10),
                child: Text(
                  '${index + 1}.',
                  style: const TextStyle(fontSize: 12),
                ),
              ),
            ),
            Expanded(child: _move(white)),
            const SizedBox(width: 8),
            Expanded(child: black == null ? const SizedBox() : _move(black)),
          ],
        );
      }),
    );
  }

  Widget _move(DiagnosticMove move) => InkWell(
    onTap: () => onTap(move.ply),
    child: Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        children: [
          if (move.classification case final quality?) ...[
            Container(
              width: 8,
              height: 8,
              decoration: BoxDecoration(
                color: qualityColor(quality),
                shape: BoxShape.circle,
              ),
            ),
            const SizedBox(width: 6),
          ],
          Expanded(
            child: Text(
              move.san,
              style: const TextStyle(fontWeight: FontWeight.w700),
            ),
          ),
          if (move.loss case final loss?)
            Text('$loss', style: const TextStyle(fontSize: 11)),
        ],
      ),
    ),
  );
}

class _EvalPainter extends CustomPainter {
  const _EvalPainter({
    required this.values,
    required this.positive,
    required this.negative,
    required this.grid,
  });
  final List<double?> values;
  final Color positive;
  final Color negative;
  final Color grid;

  @override
  void paint(Canvas canvas, Size size) {
    final middle = size.height / 2;
    canvas.drawLine(
      Offset(0, middle),
      Offset(size.width, middle),
      Paint()
        ..color = grid
        ..strokeWidth = 1,
    );
    if (values.length < 2) return;
    final path = Path();
    var started = false;
    for (var i = 0; i < values.length; i++) {
      final value = values[i];
      if (value == null) continue;
      final x = size.width * i / (values.length - 1);
      final y = middle - (value.clamp(-800, 800) / 800) * (middle - 5);
      if (!started) {
        path.moveTo(x, y);
        started = true;
      } else {
        path.lineTo(x, y);
      }
    }
    canvas.drawPath(
      path,
      Paint()
        ..color = positive
        ..strokeWidth = 2
        ..style = PaintingStyle.stroke
        ..strokeCap = StrokeCap.round,
    );
    final fill = Path.from(path)
      ..lineTo(size.width, middle)
      ..lineTo(0, middle)
      ..close();
    canvas.drawPath(fill, Paint()..color = positive.withValues(alpha: .10));
  }

  @override
  bool shouldRepaint(covariant _EvalPainter old) => old.values != values;
}

class _LinePainter extends CustomPainter {
  const _LinePainter({
    required this.values,
    required this.color,
    required this.baseline,
  });
  final List<double> values;
  final Color color;
  final double? baseline;
  @override
  void paint(Canvas canvas, Size size) {
    if (values.length < 2) return;
    final path = Path();
    for (var i = 0; i < values.length; i++) {
      final x = size.width * i / (values.length - 1);
      final y = size.height - 4 - values[i].clamp(0, 1) * (size.height - 8);
      if (i == 0) {
        path.moveTo(x, y);
      } else {
        path.lineTo(x, y);
      }
    }
    canvas.drawPath(
      path,
      Paint()
        ..color = color
        ..strokeWidth = 2
        ..style = PaintingStyle.stroke
        ..strokeCap = StrokeCap.round,
    );
  }

  @override
  bool shouldRepaint(covariant _LinePainter old) => old.values != values;
}

class _StemPainter extends CustomPainter {
  const _StemPainter({
    required this.moves,
    required this.userColor,
    required this.accent,
    required this.dark,
  });
  final List<DiagnosticMove> moves;
  final String userColor;
  final Color accent;
  final bool dark;
  @override
  void paint(Canvas canvas, Size size) {
    final timed = moves.where((move) => move.timeSpentMs != null).toList();
    if (timed.isEmpty) return;
    final maxTime = timed.map((move) => move.timeSpentMs!).fold(1, math.max);
    for (final move in timed) {
      final x = size.width * (move.ply - 1) / math.max(1, moves.length - 1);
      final height = (move.timeSpentMs! / maxTime) * (size.height - 8);
      final base = move.color == 'white'
          ? (dark ? Colors.white70 : Colors.grey.shade500)
          : (dark ? Colors.grey.shade600 : Colors.black87);
      canvas.drawLine(
        Offset(x, size.height),
        Offset(x, size.height - height),
        Paint()
          ..color = move.color == userColor ? accent : base
          ..strokeWidth = move.color == userColor ? 2.5 : 1.4,
      );
    }
  }

  @override
  bool shouldRepaint(covariant _StemPainter old) => old.moves != moves;
}

List<double> _volatility(List<DiagnosticMove> moves) {
  final values = <double>[];
  int? prior;
  for (final move in moves) {
    final current = move.evaluationCp;
    values.add(
      current == null || prior == null
          ? 0
          : ((current - prior).abs() / 500).clamp(0, 1),
    );
    if (current != null) prior = current;
  }
  return values;
}

Color qualityColor(MoveClassification value) => switch (value) {
  MoveClassification.best ||
  MoveClassification.great => const Color(0xff81b64c),
  MoveClassification.good => const Color(0xffa3c585),
  MoveClassification.inaccuracy => const Color(0xffffc840),
  MoveClassification.mistake => const Color(0xffffa459),
  MoveClassification.blunder => const Color(0xfffa412d),
};

String _label(MoveClassification value) =>
    value.name[0].toUpperCase() + value.name.substring(1);
String _moveLabel(int ply) => ply.isOdd ? '${(ply + 1) ~/ 2}.' : '${ply ~/ 2}…';
String _title(String value) => value
    .split('_')
    .map(
      (part) => part.isEmpty ? '' : part[0].toUpperCase() + part.substring(1),
    )
    .join(' ');
