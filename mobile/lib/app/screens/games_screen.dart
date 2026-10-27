import 'package:flutter/material.dart';

import '../../domain/app_controller.dart';
import '../../domain/models/game.dart';

class GamesScreen extends StatelessWidget {
  const GamesScreen({required this.controller, super.key});
  final AppController controller;

  @override
  Widget build(BuildContext context) {
    return CustomScrollView(
      slivers: [
        SliverPadding(
          padding: const EdgeInsets.fromLTRB(16, 18, 16, 8),
          sliver: SliverToBoxAdapter(
            child: Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'HISTORY',
                        style: Theme.of(context).textTheme.labelSmall
                            ?.copyWith(letterSpacing: 1.1),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        '${controller.profileGames.length} local games',
                        style: Theme.of(context).textTheme.titleLarge,
                      ),
                    ],
                  ),
                ),
                IconButton(
                  onPressed: controller.syncState == SyncState.syncing
                      ? null
                      : controller.syncGames,
                  tooltip: 'Sync Chess.com games',
                  icon: controller.syncState == SyncState.syncing
                      ? const SizedBox.square(
                          dimension: 20,
                          child: CircularProgressIndicator.adaptive(
                            strokeWidth: 2.2,
                          ),
                        )
                      : const Icon(Icons.refresh_rounded),
                ),
              ],
            ),
          ),
        ),
        if (controller.syncMessage != null)
          SliverPadding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
            sliver: SliverToBoxAdapter(
              child: _SyncNotice(
                state: controller.syncState,
                message: controller.syncMessage!,
                onDismiss: controller.clearSyncMessage,
              ),
            ),
          ),
        if (controller.profileGames.isEmpty)
          SliverFillRemaining(
            hasScrollBody: false,
            child: _EmptyGames(onAddFixture: controller.addFixtureGame),
          )
        else
          SliverPadding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            sliver: SliverList.separated(
              itemCount: controller.profileGames.length,
              separatorBuilder: (_, index) => const Divider(height: 1),
              itemBuilder: (context, index) => _GameRow(
                game: controller.profileGames[index],
                analyzing: controller.analyzingGameIds.contains(
                  controller.profileGames[index].id,
                ),
                onTap: () =>
                    controller.analyzeGame(controller.profileGames[index].id),
              ),
            ),
          ),
      ],
    );
  }
}

class _EmptyGames extends StatelessWidget {
  const _EmptyGames({required this.onAddFixture});
  final VoidCallback onAddFixture;

  @override
  Widget build(BuildContext context) => Center(
    child: Padding(
      padding: const EdgeInsets.all(32),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            Icons.sports_esports_outlined,
            size: 40,
            color: Theme.of(context).colorScheme.primary,
          ),
          const SizedBox(height: 16),
          Text(
            'Your games will live here',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 8),
          Text(
            'Add your Chess.com username in More, then refresh. Imported games remain available offline.',
            textAlign: TextAlign.center,
            style: TextStyle(
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(height: 20),
          FilledButton.icon(
            onPressed: onAddFixture,
            icon: const Icon(Icons.add),
            label: const Text('Add sample game'),
          ),
        ],
      ),
    ),
  );
}

class _SyncNotice extends StatelessWidget {
  const _SyncNotice({
    required this.state,
    required this.message,
    required this.onDismiss,
  });

  final SyncState state;
  final String message;
  final VoidCallback onDismiss;

  @override
  Widget build(BuildContext context) {
    final isError = state == SyncState.failure;
    return DecoratedBox(
      decoration: BoxDecoration(
        color: isError
            ? Theme.of(context).colorScheme.errorContainer
            : Theme.of(context).colorScheme.surfaceContainerHigh,
        borderRadius: BorderRadius.circular(6),
      ),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(12, 8, 4, 8),
        child: Row(
          children: [
            Icon(
              isError ? Icons.error_outline : Icons.check_circle_outline,
              size: 18,
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Text(message, style: const TextStyle(fontSize: 13)),
            ),
            if (state != SyncState.syncing)
              IconButton(
                onPressed: onDismiss,
                tooltip: 'Dismiss',
                visualDensity: VisualDensity.compact,
                icon: const Icon(Icons.close, size: 18),
              ),
          ],
        ),
      ),
    );
  }
}

class _GameRow extends StatelessWidget {
  const _GameRow({
    required this.game,
    required this.analyzing,
    required this.onTap,
  });
  final GameSummary game;
  final bool analyzing;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final (symbol, color) = switch (game.userResult) {
      GameResult.win => ('✓', const Color(0xff78a958)),
      GameResult.loss => ('×', const Color(0xffd36858)),
      GameResult.draw => ('–', Theme.of(context).colorScheme.onSurfaceVariant),
      GameResult.unknown => (
        '·',
        Theme.of(context).colorScheme.onSurfaceVariant,
      ),
    };
    return Semantics(
      button: true,
      label: '${game.opponent}, ${game.timeClass}',
      child: InkWell(
        onTap: analyzing ? null : onTap,
        child: SizedBox(
          height: 64,
          child: Row(
            children: [
              SizedBox(
                width: 30,
                child: Text(
                  symbol,
                  style: TextStyle(
                    color: color,
                    fontSize: 22,
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ),
              Expanded(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            game.opponent,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(fontWeight: FontWeight.w800),
                          ),
                        ),
                        if (game.opponentElo != null)
                          Text(
                            '${game.opponentElo}',
                            style: TextStyle(
                              color: Theme.of(context)
                                  .colorScheme
                                  .onSurfaceVariant,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                      ],
                    ),
                    const SizedBox(height: 3),
                    Text(
                      '${game.opening ?? 'Opening unavailable'} · ${game.timeClass}',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        fontSize: 12,
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 12),
              if (analyzing)
                const SizedBox.square(
                  dimension: 18,
                  child: CircularProgressIndicator.adaptive(strokeWidth: 2),
                )
              else
                Text(
                  game.accuracy == null
                      ? '—'
                      : '${game.accuracy!.toStringAsFixed(1)}%',
                  style: const TextStyle(fontWeight: FontWeight.w800),
                ),
            ],
          ),
        ),
      ),
    );
  }
}
