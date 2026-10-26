import 'package:flutter/material.dart';

import '../domain/app_controller.dart';
import 'theme.dart';
import 'widgets/app_shell.dart';

class ChessAnalyticsApp extends StatelessWidget {
  const ChessAnalyticsApp({required this.controller, super.key});
  final AppController controller;

  @override
  Widget build(BuildContext context) => ListenableBuilder(
    listenable: controller,
    builder: (context, _) => MaterialApp(
      title: 'Chess Analytics',
      debugShowCheckedModeBanner: false,
      theme: buildLightTheme(),
      darkTheme: buildDarkTheme(),
      themeMode: controller.settings.darkMode
          ? ThemeMode.dark
          : ThemeMode.light,
      home: AppShell(controller: controller),
    ),
  );
}
