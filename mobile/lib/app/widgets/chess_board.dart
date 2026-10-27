import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';

import '../../domain/analysis_session.dart';

const boardLight = Color(0xffeeeed2);
const boardDark = Color(0xff769657);

class ChessBoard extends StatelessWidget {
  const ChessBoard({required this.session, this.suggestionUci, super.key});
  final AnalysisSession session;
  final String? suggestionUci;

  @override
  Widget build(BuildContext context) => AspectRatio(
    aspectRatio: 1,
    child: LayoutBuilder(
      builder: (context, constraints) {
        final size = constraints.maxWidth;
        final squareSize = size / 8;
        final pieces = _pieces(session.currentFen);
        final last = session.lastMove;
        final source = last?.uci.substring(0, 2);
        final destination = last?.uci.substring(2, 4);
        return ClipRect(
          child: Stack(
            children: [
              for (var displayRank = 0; displayRank < 8; displayRank++)
                for (var displayFile = 0; displayFile < 8; displayFile++)
                  _square(
                    context,
                    displayFile,
                    displayRank,
                    squareSize,
                    source,
                    destination,
                  ),
              if (suggestionUci != null && suggestionUci!.length >= 4)
                Positioned.fill(
                  child: IgnorePointer(
                    child: CustomPaint(
                      painter: _ArrowPainter(
                        fromFile: _displayFile(suggestionUci!.substring(0, 2)),
                        fromRank: _displayRank(suggestionUci!.substring(0, 2)),
                        toFile: _displayFile(suggestionUci!.substring(2, 4)),
                        toRank: _displayRank(suggestionUci!.substring(2, 4)),
                      ),
                    ),
                  ),
                ),
              for (final entry in pieces.entries)
                Positioned(
                  left: _displayFile(entry.key) * squareSize,
                  top: _displayRank(entry.key) * squareSize,
                  width: squareSize,
                  height: squareSize,
                  child: _piece(context, entry.key, entry.value, squareSize),
                ),
              if (last?.classification != null)
                _qualityMarker(last!, squareSize),
            ],
          ),
        );
      },
    ),
  );

  Widget _piece(
    BuildContext context,
    String square,
    String piece,
    double squareSize,
  ) {
    final image = IgnorePointer(
      child: Padding(
        padding: EdgeInsets.all(squareSize * .055),
        child: SvgPicture.asset('assets/pieces/$piece.svg'),
      ),
    );
    if (square != session.motionTo || session.motionFrom == null) return image;
    final dx =
        (_displayFile(session.motionFrom!) - _displayFile(square)) * squareSize;
    final dy =
        (_displayRank(session.motionFrom!) - _displayRank(square)) * squareSize;
    return TweenAnimationBuilder<Offset>(
      key: ValueKey(session.motionSerial),
      tween: Tween(begin: Offset(dx, dy), end: Offset.zero),
      duration: MediaQuery.disableAnimationsOf(context)
          ? Duration.zero
          : const Duration(milliseconds: 165),
      curve: Curves.easeOutCubic,
      builder: (context, offset, child) =>
          Transform.translate(offset: offset, child: child),
      child: image,
    );
  }

  Widget _square(
    BuildContext context,
    int displayFile,
    int displayRank,
    double size,
    String? source,
    String? destination,
  ) {
    final file = session.flipped ? 7 - displayFile : displayFile;
    final rank = session.flipped ? displayRank : 7 - displayRank;
    final square = '${String.fromCharCode(97 + file)}${rank + 1}';
    final selected = session.selectedSquare == square;
    final legal = session.legalTargets.contains(square);
    final lastSource = square == source;
    final lastDestination = square == destination;
    return Positioned(
      left: displayFile * size,
      top: displayRank * size,
      width: size,
      height: size,
      child: GestureDetector(
        key: ValueKey('square-$square'),
        onTap: () => session.selectSquare(square),
        child: ColoredBox(
          color: (file + rank).isEven ? boardDark : boardLight,
          child: Stack(
            children: [
              if (lastSource)
                const Positioned.fill(
                  child: ColoredBox(color: Color(0x55f6f669)),
                ),
              if (lastDestination)
                const Positioned.fill(
                  child: ColoredBox(color: Color(0x88f6f669)),
                ),
              if (selected)
                const Positioned.fill(
                  child: ColoredBox(color: Color(0x6678b4d8)),
                ),
              if (legal)
                Center(
                  child: Container(
                    width: size * .24,
                    height: size * .24,
                    decoration: const BoxDecoration(
                      color: Color(0x66404935),
                      shape: BoxShape.circle,
                    ),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _qualityMarker(SessionMove move, double squareSize) {
    final square = move.uci.substring(2, 4);
    final color = switch (move.classification) {
      'best' || 'great' => const Color(0xff81b64c),
      'good' => const Color(0xffa3be72),
      'inaccuracy' => const Color(0xffffc84a),
      'mistake' => const Color(0xffff9f43),
      _ => const Color(0xffe4574f),
    };
    final symbol = switch (move.classification) {
      'best' || 'great' => '★',
      'good' => '✓',
      'inaccuracy' => '?!',
      'mistake' => '?',
      _ => '??',
    };
    return Positioned(
      left: _displayFile(square) * squareSize + squareSize * .68,
      top: _displayRank(square) * squareSize + squareSize * .05,
      child: Container(
        width: squareSize * .27,
        height: squareSize * .27,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: color,
          shape: BoxShape.circle,
          border: Border.all(
            color: Colors.black.withValues(alpha: .22),
            width: .5,
          ),
        ),
        child: FittedBox(
          child: Text(
            symbol,
            style: const TextStyle(
              color: Colors.white,
              fontWeight: FontWeight.w900,
              fontSize: 10,
            ),
          ),
        ),
      ),
    );
  }

  int _displayFile(String square) {
    final file = square.codeUnitAt(0) - 97;
    return session.flipped ? 7 - file : file;
  }

  int _displayRank(String square) {
    final rank = int.parse(square[1]) - 1;
    return session.flipped ? rank : 7 - rank;
  }

  Map<String, String> _pieces(String fen) {
    final result = <String, String>{};
    final ranks = fen.split(' ').first.split('/');
    for (var rankIndex = 0; rankIndex < 8; rankIndex++) {
      var file = 0;
      for (final token in ranks[rankIndex].split('')) {
        final empty = int.tryParse(token);
        if (empty != null) {
          file += empty;
          continue;
        }
        final color = token == token.toUpperCase() ? 'w' : 'b';
        result['${String.fromCharCode(97 + file)}${8 - rankIndex}'] =
            '$color${token.toLowerCase()}';
        file++;
      }
    }
    return result;
  }
}

class _ArrowPainter extends CustomPainter {
  const _ArrowPainter({
    required this.fromFile,
    required this.fromRank,
    required this.toFile,
    required this.toRank,
  });
  final int fromFile;
  final int fromRank;
  final int toFile;
  final int toRank;

  @override
  void paint(Canvas canvas, Size size) {
    final unit = size.width / 8;
    final start = Offset((fromFile + .5) * unit, (fromRank + .5) * unit);
    final end = Offset((toFile + .5) * unit, (toRank + .5) * unit);
    final paint = Paint()
      ..color = const Color(0xaae6b94a)
      ..strokeWidth = unit * .13
      ..strokeCap = StrokeCap.round;
    canvas.drawLine(start, end, paint);
    final direction = start - end;
    final normalized = direction / direction.distance;
    final perpendicular = Offset(-normalized.dy, normalized.dx);
    final tipBack = end + normalized * unit * .30;
    final path = Path()
      ..moveTo(end.dx, end.dy)
      ..lineTo(
        (tipBack + perpendicular * unit * .18).dx,
        (tipBack + perpendicular * unit * .18).dy,
      )
      ..lineTo(
        (tipBack - perpendicular * unit * .18).dx,
        (tipBack - perpendicular * unit * .18).dy,
      )
      ..close();
    canvas.drawPath(path, paint..style = PaintingStyle.fill);
  }

  @override
  bool shouldRepaint(covariant _ArrowPainter oldDelegate) =>
      oldDelegate.fromFile != fromFile ||
      oldDelegate.fromRank != fromRank ||
      oldDelegate.toFile != toFile ||
      oldDelegate.toRank != toRank;
}
