import 'package:flutter/material.dart';

const _green = Color(0xff769656);

ThemeData buildLightTheme() => ThemeData(
  useMaterial3: true,
  colorScheme: ColorScheme.fromSeed(
    seedColor: _green,
    surface: const Color(0xfff6f6f2),
  ),
  scaffoldBackgroundColor: const Color(0xfff6f6f2),
  navigationBarTheme: _navigationTheme(const Color(0xffdfe9d3)),
  textTheme: _textTheme,
);

ThemeData buildDarkTheme() => ThemeData(
  useMaterial3: true,
  colorScheme: ColorScheme.fromSeed(
    seedColor: const Color(0xff96b86f),
    brightness: Brightness.dark,
    surface: const Color(0xff24251f),
  ),
  scaffoldBackgroundColor: const Color(0xff1d1e1a),
  navigationBarTheme: _navigationTheme(const Color(0xff3b4930)),
  textTheme: _textTheme,
);

const _textTheme = TextTheme(
  headlineMedium: TextStyle(fontWeight: FontWeight.w800),
  titleLarge: TextStyle(fontWeight: FontWeight.w800),
  titleMedium: TextStyle(fontWeight: FontWeight.w700),
);

NavigationBarThemeData _navigationTheme(Color indicator) =>
    NavigationBarThemeData(
      height: 68,
      indicatorColor: indicator,
      labelTextStyle: const WidgetStatePropertyAll(
        TextStyle(fontSize: 11, fontWeight: FontWeight.w700),
      ),
    );
