import 'package:flutter/material.dart';

import 'screens/home.dart';
import 'screens/login.dart';
import 'services/api_client.dart';
import 'services/auth_service.dart';
import 'services/token_storage.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const MyApp());
}

class MyApp extends StatefulWidget {
  const MyApp({super.key});

  @override
  State<MyApp> createState() => _MyAppState();
}

class _MyAppState extends State<MyApp> {
  late final ApiClient _api;
  late final AuthService _auth;

  Map<String, dynamic>? _user;

  @override
  void initState() {
    super.initState();
    _api = ApiClient(tokenStorage: TokenStorage());
    _auth = AuthService(_api);
  }

  @override
  void dispose() {
    _api.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Veterinary Dental Care',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.teal),
        useMaterial3: true,
      ),
      home: _user == null
          ? LoginScreen(
              auth: _auth,
              onLoggedIn: (user) {
                setState(() => _user = user);
              },
            )
          : HomeScreen(
              user: _user!,
              auth: _auth,
              onLoggedOut: () {
                setState(() => _user = null);
              },
            ),
    );
  }
}