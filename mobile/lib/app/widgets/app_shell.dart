import 'package:flutter/material.dart';

import '../../domain/app_controller.dart';
import '../screens/games_screen.dart';
import '../screens/more_screen.dart';
import '../screens/placeholder_screen.dart';

class AppShell extends StatefulWidget {
  const AppShell({required this.controller, super.key});
  final AppController controller;

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  int _index = 2;

  @override
  Widget build(BuildContext context) {
    final controller = widget.controller;
    if (controller.state == LoadState.loading ||
        controller.state == LoadState.idle) {
      return const Scaffold(
        body: Center(child: CircularProgressIndicator.adaptive()),
      );
    }
    if (controller.state == LoadState.failure) {
      return Scaffold(
        body: SafeArea(
          child: Center(
            child: Padding(
              padding: const EdgeInsets.all(28),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(Icons.error_outline, size: 38),
                  const SizedBox(height: 14),
                  const Text(
                    'Local data could not be opened.',
                    style: TextStyle(fontWeight: FontWeight.w800),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    controller.errorMessage ?? 'Unknown error',
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 18),
                  FilledButton(
                    onPressed: controller.initialize,
                    child: const Text('Try again'),
                  ),
                ],
              ),
            ),
          ),
        ),
      );
    }

    final pages = [
      const PlaceholderScreen(
        icon: Icons.home_outlined,
        label: 'Home',
        message: 'Your local performance portrait will live here.',
      ),
      const PlaceholderScreen(
        icon: Icons.menu_book_outlined,
        label: 'Openings',
        message: 'The offline-capable explorer arrives after local analysis.',
      ),
      GamesScreen(controller: controller),
      const PlaceholderScreen(
        icon: Icons.insights_outlined,
        label: 'Insights',
        message: 'Local insights will be derived from analyzed games.',
      ),
      MoreScreen(controller: controller),
    ];
    return Scaffold(
      body: SafeArea(
        bottom: false,
        child: IndexedStack(index: _index, children: pages),
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (value) => setState(() => _index = value),
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.home_outlined),
            selectedIcon: Icon(Icons.home),
            label: 'Home',
          ),
          NavigationDestination(
            icon: Icon(Icons.menu_book_outlined),
            selectedIcon: Icon(Icons.menu_book),
            label: 'Openings',
          ),
          NavigationDestination(
            icon: Icon(Icons.sports_esports_outlined),
            selectedIcon: Icon(Icons.sports_esports),
            label: 'Games',
          ),
          NavigationDestination(
            icon: Icon(Icons.insights_outlined),
            selectedIcon: Icon(Icons.insights),
            label: 'Insights',
          ),
          NavigationDestination(icon: Icon(Icons.more_horiz), label: 'More'),
        ],
      ),
    );
  }
}
