import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'presentation/screens/navigation_map_screen.dart';

void main() {
  runApp(
    const ProviderScope(
      child: SensePathApp(),
    ),
  );
}

class SensePathApp extends StatelessWidget {
  const SensePathApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'SensePath',
      theme: ThemeData(
        brightness: Brightness.dark,
        primarySwatch: Colors.deepPurple,
        scaffoldBackgroundColor: const Color(0xFF121212),
        useMaterial3: true,
      ),
      home: const NavigationMapScreen(),
      debugShowCheckedModeBanner: false,
    );
  }
}
