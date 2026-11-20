import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';

class PhoneNotificationService {
  PhoneNotificationService._();

  static final instance = PhoneNotificationService._();

  static const channelId = 'vetdental_updates';
  static const channelName = 'VetDental updates';

  final _plugin = FlutterLocalNotificationsPlugin();
  Future<void>? _initialization;

  ValueChanged<String?>? onTap;
  String? _launchPayload;

  bool get supported =>
      !kIsWeb && defaultTargetPlatform == TargetPlatform.android;

  Future<void> initialize() async {
    if (!supported) return;

    _initialization ??= _initialize();

    try {
      await _initialization;
    } catch (_) {
      _initialization = null;
      rethrow;
    }
  }

  Future<void> _initialize() async {
    await _plugin.initialize(
      const InitializationSettings(
        android: AndroidInitializationSettings(
          'ic_stat_vetdental',
        ),
      ),
      onDidReceiveNotificationResponse: (response) {
        onTap?.call(response.payload);
      },
    );

    final android = _plugin.resolvePlatformSpecificImplementation<
        AndroidFlutterLocalNotificationsPlugin>();

    await android?.createNotificationChannel(
      const AndroidNotificationChannel(
        channelId,
        channelName,
        description: 'Appointment, order and care updates',
        importance: Importance.high,
      ),
    );

    final launch = await _plugin.getNotificationAppLaunchDetails();
    if (launch?.didNotificationLaunchApp == true) {
      _launchPayload = launch?.notificationResponse?.payload;
    }
  }

  String? takeLaunchPayload() {
    final payload = _launchPayload;
    _launchPayload = null;
    return payload;
  }

  Future<bool> requestPermission() async {
    if (!supported) return false;
    await initialize();

    final android = _plugin.resolvePlatformSpecificImplementation<
        AndroidFlutterLocalNotificationsPlugin>();

    return await android?.requestNotificationsPermission() ?? false;
  }

  Future<void> show({
    required int id,
    required String title,
    required String body,
    String? payload,
    bool Function()? canShow,
  }) async {
    if (!supported) return;
    await initialize();

    final android = _plugin.resolvePlatformSpecificImplementation<
        AndroidFlutterLocalNotificationsPlugin>();

    if (await android?.areNotificationsEnabled() != true) return;

    if (canShow != null && !canShow()) return;

    await _plugin.show(
      id,
      title,
      body,
      const NotificationDetails(
        android: AndroidNotificationDetails(
          channelId,
          channelName,
          channelDescription: 'Appointment, order and care updates',
          icon: 'ic_stat_vetdental',
          importance: Importance.high,
          priority: Priority.high,
          visibility: NotificationVisibility.private,
          autoCancel: true,
          onlyAlertOnce: true,
        ),
      ),
      payload: payload,
    );
  }

  Future<void> cancelAll() async {
    if (!supported) return;
    await initialize();
    await _plugin.cancelAll();
  }
}