import 'dart:async';

import 'package:flutter/material.dart';

import '../services/notification_service.dart';
import 'notifications.dart';

class OwnerNotificationBell extends StatefulWidget {
  final NotificationService service;
  final bool enabled;

  const OwnerNotificationBell({
    super.key,
    required this.service,
    this.enabled = true,
  });

  @override
  State<OwnerNotificationBell> createState() =>
      _OwnerNotificationBellState();
}

class _OwnerNotificationBellState
    extends State<OwnerNotificationBell>
    with WidgetsBindingObserver {
  Timer? _timer;
  int? _unreadCount;
  bool _loading = false;
  bool _opening = false;

  @override
  void initState() {
    super.initState();

    WidgetsBinding.instance.addObserver(this);

    _refreshCount();

    _timer = Timer.periodic(
      const Duration(seconds: 30),
          (_) {
        if (!_opening) {
          _refreshCount();
        }
      },
    );
  }

  @override
  void dispose() {
    _timer?.cancel();
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didUpdateWidget(covariant OwnerNotificationBell oldWidget) {
    super.didUpdateWidget(oldWidget);

    if (widget.enabled && !oldWidget.enabled) {
      _refreshCount();
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      _refreshCount();
    }
  }

  Future<void> _refreshCount() async {
    if (!mounted || _loading || !widget.enabled) return;

    final lifecycle = WidgetsBinding.instance.lifecycleState;

    if (lifecycle != null &&
        lifecycle != AppLifecycleState.resumed) {
      return;
    }

    _loading = true;

    try {
      final count = await widget.service.getUnreadCount();

      if (mounted) {
        setState(() => _unreadCount = count);
      }
    } catch (_) {
      // Hide an uncertain count rather than displaying a false zero.
      if (mounted) {
        setState(() => _unreadCount = null);
      }
    } finally {
      _loading = false;
    }
  }

  Future<void> _openNotifications() async {
    if (_opening || !widget.enabled) return;

    setState(() => _opening = true);

    try {
      await Navigator.of(context).push<void>(
        MaterialPageRoute(
          builder: (_) => OwnerNotificationsScreen(
            service: widget.service,
          ),
        ),
      );
    } finally {
      if (mounted) {
        setState(() => _opening = false);
        await _refreshCount();
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final count = _unreadCount ?? 0;

    return IconButton(
      tooltip: count > 0
          ? 'Notifications — $count unread'
          : 'Notifications',
      onPressed: widget.enabled && !_opening
          ? _openNotifications
          : null,
      icon: SizedBox(
        width: 34,
        height: 32,
        child: Stack(
          clipBehavior: Clip.none,
          children: [
            const Center(
              child: Icon(Icons.notifications_outlined),
            ),
            if (count > 0)
              Positioned(
                top: -2,
                right: -5,
                child: Container(
                  constraints: const BoxConstraints(
                    minWidth: 18,
                    minHeight: 18,
                  ),
                  padding: const EdgeInsets.symmetric(
                    horizontal: 4,
                    vertical: 2,
                  ),
                  decoration: BoxDecoration(
                    color: const Color(0xFFB3261E),
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(
                      color: Colors.white,
                      width: 1.5,
                    ),
                  ),
                  child: Text(
                    count > 99 ? '99+' : '$count',
                    textAlign: TextAlign.center,
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 10,
                      height: 1,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}