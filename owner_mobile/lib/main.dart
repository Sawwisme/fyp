import 'package:flutter/material.dart';
import 'theme/app_theme.dart';

import 'screens/home.dart';
import 'screens/login.dart';
import 'services/api_client.dart';
import 'services/auth_service.dart';
import 'services/token_storage.dart';
import 'package:flutter_localizations/flutter_localizations.dart';

import 'dart:convert';

import 'services/notification_service.dart';
import 'services/phone_notification_service.dart';
import 'screens/notifications.dart';


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

  final GlobalKey<NavigatorState> _navigatorKey = GlobalKey<NavigatorState>();

  final PhoneNotificationService _phone = PhoneNotificationService.instance;

  int? _pendingNotificationId;
  int? _pendingNotificationUserId;
  bool _openingNotification = false;

  void _handleNotificationTap(String? payload) {
    if (payload == null || payload.isEmpty) return;

    try {
      final decoded = jsonDecode(payload);

      if (decoded is! Map) return;

      final notificationId = decoded['notification_id'];
      final userId = decoded['user_id'];

      if (notificationId is! int ||
          notificationId < 1 ||
          notificationId > 2147483647 ||
          userId is! int ||
          userId < 1) {
        return;
      }

      _pendingNotificationId = notificationId;
      _pendingNotificationUserId = userId;

      _schedulePendingNotification();
    } catch (_) {
      // Ignore malformed or unrelated notification payloads.
    }
  }

  void _schedulePendingNotification() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      _openPendingNotification();
    });
  }

  Future<void> _openPendingNotification() async {
    if (_openingNotification ||
        _restoring ||
        _restoreError != null ||
        _user == null) {
      return;
    }

    final notificationId = _pendingNotificationId;
    final targetUserId = _pendingNotificationUserId;

    if (notificationId == null || targetUserId == null) {
      return;
    }

    final currentUserId = _user!['user_id'];

    // Never route a notification belonging to another account.
    if (currentUserId != targetUserId) {
      _pendingNotificationId = null;
      _pendingNotificationUserId = null;


      final context = _navigatorKey.currentContext;

      if (context != null) {
        ScaffoldMessenger.maybeOf(context)?.showSnackBar(
          const SnackBar(
            content: Text(
              'This notification belongs to another account.',
            ),
          ),
        );
      }


      return;
    }

    final navigator = _navigatorKey.currentState;

    if (navigator == null) {
      _schedulePendingNotification();
      return;
    }

    _openingNotification = true;

    // Consume before navigation to prevent duplicate opening.
    _pendingNotificationId = null;
    _pendingNotificationUserId = null;

    try {
      await navigator.push<void>(
        MaterialPageRoute(
          builder: (_) => OwnerNotificationsScreen(
            service: NotificationService(_api),
            initialNotificationId: notificationId,
          ),
        ),
      );
    } finally {
      _openingNotification = false;

      if (_pendingNotificationId != null && mounted) {
        _schedulePendingNotification();
      }
    }
  }



  @override
  void initState() {
    super.initState();

    _api = ApiClient(tokenStorage: TokenStorage());
    _auth = AuthService(_api);

    _phone.onTap = _handleNotificationTap;

    _initializeNotificationNavigation();
    _restoreSession();
  }

  Future<void> _initializeNotificationNavigation() async {
    try {
      await _phone.initialize();

      final launchPayload = _phone.takeLaunchPayload();

      if (mounted && launchPayload != null) {
        _handleNotificationTap(launchPayload);
      }
    } catch (error) {
      debugPrint(
        'Notification navigation initialization failed: $error',
      );
    }
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
        _schedulePendingNotification();
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
          _schedulePendingNotification();
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
    _phone.onTap = null;
    _api.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      navigatorKey: _navigatorKey,
      title: 'Veterinary Dental Care',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light,
      home: _buildHome(),
      localizationsDelegates:
      GlobalMaterialLocalizations.delegates,
      supportedLocales: const [
        Locale('en'),
        Locale('ms'),
        Locale('zh', 'CN'),
      ],
    );
  }
}