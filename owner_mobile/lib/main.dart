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
  bool _restoring = true;
  String? _restoreError;

  @override
  void initState() {
    super.initState();
    _api = ApiClient(tokenStorage: TokenStorage());
    _auth = AuthService(_api);
    _restoreSession();
  }

  Future<void> _restoreSession() async {
    setState(() {
      _restoring = true;
      _restoreError = null;
    });

    try {
      final token = await _api.tokenStorage.readToken();

      if (token == null || token.isEmpty) return;

      final user = await _auth.getCurrentUser();

      if (user['role'] != 'pet_owner') {
        throw const ApiException(
          'This application is for pet owners.',
          statusCode: 403,
        );
      }

      if (mounted) {
        setState(() => _user = user);
      }
    } on ApiException catch (error) {
      if (error.statusCode == 401 || error.statusCode == 403) {
        try {
          await _auth.logout();
        } catch (_) {
          if (mounted) {
            setState(() {
              _restoreError = 'Unable to clear the saved login.';
            });
          }
        }
      } else if (mounted) {
        setState(() => _restoreError = error.message);
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          _restoreError = 'Unable to restore your login. Please try again.';
        });
      }
    } finally {
      if (mounted) {
        setState(() => _restoring = false);
      }
    }
  }

  Future<void> _startFreshLogin() async {
    try {
      await _auth.logout();

      if (!mounted) return;

      setState(() {
        _user = null;
        _restoreError = null;
      });
    } catch (_) {
      if (mounted) {
        setState(() {
          _restoreError = 'Unable to clear the saved login. Please retry.';
        });
      }
    }
  }

  Widget _buildHome() {
    if (_restoring) {
      return const Scaffold(
        body: Center(child: CircularProgressIndicator()),
      );
    }

    if (_restoreError != null) {
      return Scaffold(
        appBar: AppBar(title: const Text('Veterinary Dental Care')),
        body: Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  _restoreError!,
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 16),
                FilledButton(
                  onPressed: _restoreSession,
                  child: const Text('Retry'),
                ),
                TextButton(
                  onPressed: _startFreshLogin,
                  child: const Text('Go to login'),
                ),
              ],
            ),
          ),
        ),
      );
    }

    if (_user == null) {
      return LoginScreen(
        auth: _auth,
        onLoggedIn: (user) {
          setState(() => _user = user);
        },
      );
    }

    return HomeScreen(
      user: _user!,
      auth: _auth,
      onLoggedOut: () {
        setState(() => _user = null);
      },
    );
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
      home: _buildHome(),
    );
  }
}