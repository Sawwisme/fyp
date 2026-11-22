import 'package:flutter/material.dart';

import '../services/checkout_service.dart';
import '../services/notification_service.dart';
import 'shop_order_details.dart';
import '../services/billing_service.dart';
import 'bill_details.dart';
import '../services/ai_assessment_review_service.dart';
import 'ai_assessment_reviews.dart';
import '../services/appointment_service.dart';
import 'appointment_details.dart';
import '../services/dental_assessment_service.dart';
import '../services/pet_service.dart';
import 'ai_scan.dart';
import '../services/phone_notification_service.dart';

class OwnerNotificationsScreen extends StatefulWidget {
  final NotificationService service;
  final int? initialNotificationId;

  const OwnerNotificationsScreen({
    super.key,
    required this.service,
    this.initialNotificationId,
  });

  @override
  State<OwnerNotificationsScreen> createState() =>
      _OwnerNotificationsScreenState();
}

class _OwnerNotificationsScreenState extends State<OwnerNotificationsScreen> {
  static const _green = Color(0xFF2549C7);
  static const _pageSize = 20;
  bool _openingResource = false;

  List<Map<String, dynamic>> _items = [];
  int _page = 0;
  bool _hasMore = false;
  bool _loading = false;
  int? _readingId;
  String? _error;

  bool get _busy =>
      _loading || _readingId != null || _openingResource;


  @override
  void initState() {
    super.initState();

    _load();

    final notificationId = widget.initialNotificationId;

    if (notificationId != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!mounted) return;

        _openBannerNotification(notificationId);
      });
    }
  }

  bool _enablingAlerts = false;


  bool _handlingBanner = false;

  Future<void> _openNotificationRecord(
      Map<String, dynamic> item,
      ) async {
    switch (item['resource_type']) {
      case 'shop_order':
        await _openOrder(item);
        break;

      case 'consultation_bill':
        await _openBill(item);
        break;

      case 'ai_assessment_review':
        await _openAIReview(item);
        break;

      case 'appointment':
        await _openAppointment(item);
        break;

      case 'emergency_request':
        await _openEmergencyRequest(item);
        break;

      case 'dental_assessment':
        await _openAssessment(item);
        break;

      default:
        if (!mounted) return;

        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'This notification has no detail page.',
            ),
          ),
        );
    }
  }

  Future<void> _openBannerNotification(
      int notificationId,
      ) async {
    if (_handlingBanner || !mounted) return;

    _handlingBanner = true;

    try {
      final notification =
      await widget.service.getNotificationById(
        notificationId,
      );

      if (!mounted) return;

      // The existing record-opening methods require
      // the screen not to be in its loading state.
      while (_loading && mounted) {
        await Future<void>.delayed(
          const Duration(milliseconds: 100),
        );
      }

      if (!mounted) return;

      await _openNotificationRecord(notification);
    } catch (error) {
      if (!mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            'Could not open notification: $error',
          ),
        ),
      );
    } finally {
      _handlingBanner = false;
    }
  }

  Future<void> _enablePhoneAlerts() async {
    if (_busy || _enablingAlerts) return;

    setState(() => _enablingAlerts = true);

    try {
      final phone = PhoneNotificationService.instance;

      if (!phone.supported) {
        throw Exception('Phone alerts currently support Android.');
      }

      final allowed = await phone.requestPermission();

      if (!mounted) return;

      if (!allowed) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'Notifications are disabled. Enable them in Android app settings.',
            ),
          ),
        );
        return;
      }

      await phone.show(
        id: 0,
        title: 'VetDental alerts enabled',
        body: 'Your phone can display VetDental notification banners.',
      );
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Could not enable phone alerts: $error')),
        );
      }
    } finally {
      if (mounted) setState(() => _enablingAlerts = false);
    }
  }

  String _date(dynamic value) {
    final parsed = DateTime.tryParse(value?.toString() ?? '');
    if (parsed == null) return '—';

    final date = parsed.toUtc().add(const Duration(hours: 8));
    String two(int number) => number.toString().padLeft(2, '0');

    return '${two(date.day)}/${two(date.month)}/${date.year} '
        '${two(date.hour)}:${two(date.minute)} MYT';
  }

  Future<void> _load([int page = 0]) async {
    if (_busy) return;

    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final items = await widget.service.getNotifications(
        offset: page * _pageSize,
        limit: _pageSize + 1,
      );

      if (!mounted) return;

      setState(() {
        _items = items.take(_pageSize).toList();
        _hasMore = items.length > _pageSize;
        _page = page;
      });
    } catch (error) {
      if (mounted) {
        setState(() => _error = error.toString());
      }
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  Future<void> _markRead(Map<String, dynamic> item) async {
    if (_busy || item['read_at'] != null) return;

    final id = item['notification_id'] as int;
    setState(() => _readingId = id);

    try {
      final saved = await widget.service.markRead(id);

      if (!mounted) return;

      setState(() {
        final index = _items.indexWhere(
              (entry) => entry['notification_id'] == id,
        );

        if (index >= 0) {
          _items[index] = saved;
        }
      });
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Could not mark as read: $error'),
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _readingId = null);
      }
    }
  }

  Future<void> _openOrder(Map<String, dynamic> item) async {
    if (_busy) return;

    final orderId = item['resource_id'];

    if (item['resource_type'] != 'shop_order' ||
        orderId is! int ||
        orderId < 1) {
      return;
    }

    await _markRead(item);
    if (!mounted) return;

    await Navigator.of(context).push<void>(
      MaterialPageRoute(
        builder: (_) => ShopOrderDetailsScreen(
          service: CheckoutService(widget.service.api),
          orderId: orderId,
        ),
      ),
    );

    if (mounted) {
      await _load(_page);
    }
  }

  Future<void> _openBill(Map<String, dynamic> item) async {
    if (_busy) return;

    final billId = item['resource_id'];

    if (item['resource_type'] != 'consultation_bill' ||
        billId is! int ||
        billId < 1) {
      return;
    }

    await _markRead(item);
    if (!mounted) return;

    await Navigator.of(context).push<void>(
      MaterialPageRoute(
        builder: (_) => BillDetailsScreen(
          service: BillingService(widget.service.api),
          billId: billId,
        ),
      ),
    );

    if (mounted) {
      await _load(_page);
    }
  }

  Future<void> _openAIReview(Map<String, dynamic> item) async {
    if (_busy) return;

    final reviewId = item['resource_id'];

    if (item['resource_type'] != 'ai_assessment_review' ||
        reviewId is! int ||
        reviewId < 1 ||
        reviewId > 2147483647) {
      return;
    }

    await _markRead(item);
    if (!mounted) return;

    await Navigator.of(context).push<void>(
      MaterialPageRoute(
        builder: (_) => AIAssessmentReviewsScreen(
          service: AIAssessmentReviewService(widget.service.api),
          reviewId: reviewId,
        ),
      ),
    );

    if (mounted) {
      await _load(_page);
    }
  }

  Future<void> _openAppointment(Map<String, dynamic> item) async {
    if (_busy) return;

    final appointmentId = item['resource_id'];

    if (item['resource_type'] != 'appointment' ||
        appointmentId is! int ||
        appointmentId < 1 ||
        appointmentId > 2147483647) {
      return;
    }

    setState(() => _openingResource = true);
    var opened = false;

    try {
      final service = AppointmentService(widget.service.api);

      // Fetch through the owner-authorised appointment API.
      final appointment = await service.getMyAppointmentById(
        appointmentId,
      );

      if (!mounted) return;

      if (appointment == null) {
        throw Exception('This appointment is no longer available.');
      }

      if (item['read_at'] == null) {
        final saved = await widget.service.markRead(
          item['notification_id'] as int,
        );

        if (!mounted) return;

        setState(() {
          final index = _items.indexWhere(
                (entry) =>
            entry['notification_id'] == item['notification_id'],
          );
          if (index >= 0) _items[index] = saved;
        });
      }

      if (!mounted) return;

      await Navigator.of(context).push<void>(
        MaterialPageRoute(
          builder: (_) => AppointmentDetailsScreen(
            appointment: appointment,
            service: service,
          ),
        ),
      );

      opened = true;
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Could not open appointment: $error'),
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _openingResource = false);
      }
    }

    if (mounted && opened) await _load(_page);
  }

  Future<void> _openEmergencyRequest(
      Map<String, dynamic> item,
      ) async {
    if (_busy) return;

    final requestId = item['resource_id'];
    if (item['resource_type'] != 'emergency_request' ||
        requestId is! int ||
        requestId < 1 ||
        requestId > 2147483647) {
      return;
    }

    setState(() => _openingResource = true);

    try {
      final service = AppointmentService(widget.service.api);
      Map<String, dynamic>? request;

      for (var offset = 0; ; offset += 100) {
        final page = await service.getMyEmergencyRequests(
          offset: offset,
          limit: 100,
        );

        for (final candidate in page) {
          if (candidate['emergency_appointment_id'] == requestId) {
            request = candidate;
            break;
          }
        }

        if (request != null || page.length < 100) break;
      }

      if (!mounted) return;

      if (request == null) {
        throw Exception('This emergency request is unavailable.');
      }

      if (item['read_at'] == null) {
        final saved = await widget.service.markRead(
          item['notification_id'] as int,
        );
        if (!mounted) return;

        setState(() {
          final index = _items.indexWhere(
                (entry) =>
            entry['notification_id'] == item['notification_id'],
          );
          if (index >= 0) _items[index] = saved;
        });
      }

      final details = request;

      if (!mounted) return;

      await showModalBottomSheet<void>(
        context: context,
        isScrollControlled: true,
        builder: (_) => SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Emergency request #$requestId',
                  style: const TextStyle(
                    fontSize: 20,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 16),
                Text('Pet: ${details['pet_name']}'),
                Text('Clinic: ${details['clinic_name']}'),
                Text(
                  'Status: ${details['approval_status']}',
                ),
                const SizedBox(height: 16),
                const Text(
                  'Clinic’s recorded reason',
                  style: TextStyle(fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 8),
                Text(
                  details['rejection_reason']?.toString() ??
                      'No rejection reason recorded.',
                ),
              ],
            ),
          ),
        ),
      );
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Could not open request: $error')),
        );
      }
    } finally {
      if (mounted) setState(() => _openingResource = false);
    }
  }

  Future<void> _openAssessment(Map<String, dynamic> item) async {
    if (_busy) return;

    final jobId = item['resource_id'];
    if (item['resource_type'] != 'dental_assessment' ||
        jobId is! int ||
        jobId < 1 ||
        jobId > 2147483647) {
      return;
    }

    setState(() => _openingResource = true);
    var opened = false;

    try {
      final service = DentalAssessmentService(widget.service.api);

      // The backend checks ownership before returning this assessment.
      final job = await service.getAssessment(jobId);
      final petId = job['pet_id'];

      if (petId is! int || petId < 1) {
        throw Exception('The assessment pet could not be verified.');
      }

      if (!mounted) return;

      if (item['read_at'] == null) {
        final saved = await widget.service.markRead(
          item['notification_id'] as int,
        );

        if (!mounted) return;

        setState(() {
          final index = _items.indexWhere(
                (entry) =>
            entry['notification_id'] == item['notification_id'],
          );
          if (index >= 0) _items[index] = saved;
        });
      }

      if (!mounted) return;

      await Navigator.of(context).push<void>(
        MaterialPageRoute(
          builder: (_) => Scaffold(
            appBar: AppBar(
              title: const Text('Dental assessment'),
            ),
            body: AiScanPage(
              petService: PetService(widget.service.api),
              service: service,
              initialPetId: petId,
              initialAssessmentJobId: jobId,
            ),
          ),
        ),
      );

      opened = true;
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Could not open assessment: $error')),
        );
      }
    } finally {
      if (mounted) setState(() => _openingResource = false);
    }

    if (mounted && opened) await _load(_page);
  }

  Widget _card(Map<String, dynamic> item) {
    final unread = item['read_at'] == null;
    final aiReview =
        item['resource_type'] == 'ai_assessment_review';
    final shopOrder = item['resource_type'] == 'shop_order';
    final consultationBill =
        item['resource_type'] == 'consultation_bill';
    final appointment = item['resource_type'] == 'appointment';
    final emergencyRequest =
        item['resource_type'] == 'emergency_request';
    final assessment =
        item['resource_type'] == 'dental_assessment';
    final reading = _readingId == item['notification_id'];

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(
          color: unread
              ? const Color(0xFFA9CFB2)
              : const Color(0xFFDDE7DF),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Text(
                  item['title']?.toString() ?? 'Update',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: unread
                        ? FontWeight.bold
                        : FontWeight.w600,
                  ),
                ),
              ),
              if (unread) ...[
                const SizedBox(width: 12),
                const Padding(
                  padding: EdgeInsets.only(top: 5),
                  child: CircleAvatar(
                    radius: 4,
                    backgroundColor: _green,
                  ),
                ),
              ],
            ],
          ),
          const SizedBox(height: 10),
          Text(
            item['message']?.toString() ?? '',
            style: const TextStyle(height: 1.5),
          ),
          const SizedBox(height: 12),
          Text(
            _date(item['created_at']),
            style: const TextStyle(
              color: Colors.black54,
              fontSize: 12,
            ),
          ),
          if (shopOrder ||
              consultationBill ||
              aiReview ||
              appointment ||
              emergencyRequest ||
              assessment ||
              unread) ...[
            const SizedBox(height: 12),
            Wrap(
              spacing: 10,
              runSpacing: 8,
              children: [
                if (assessment)
                  OutlinedButton(
                    onPressed: _busy
                        ? null
                        : () => _openAssessment(item),
                    child: const Text('View assessment'),
                  ),
                if (emergencyRequest)
                  OutlinedButton(
                    onPressed: _busy
                        ? null
                        : () => _openEmergencyRequest(item),
                    child: const Text('View emergency request'),
                  ),
                if (appointment)
                  OutlinedButton(
                    onPressed: _busy
                        ? null
                        : () => _openAppointment(item),
                    child: const Text('View appointment'),
                  ),
                if (aiReview)
                  OutlinedButton(
                    onPressed: _busy
                        ? null
                        : () => _openAIReview(item),
                    child: const Text('View vet feedback'),
                  ),
                if (shopOrder)
                  OutlinedButton(
                    onPressed: _busy
                        ? null
                        : () => _openOrder(item),
                    child: const Text('View order'),
                  ),
                if (consultationBill)
                  OutlinedButton(
                    onPressed: _busy
                        ? null
                        : () => _openBill(item),
                    child: const Text('View bill'),
                  ),
                if (unread)
                  TextButton(
                    onPressed: _busy
                        ? null
                        : () => _markRead(item),
                    child: Text(
                      reading ? 'Saving…' : 'Mark as read',
                    ),
                  ),
              ],
            ),
          ],
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFEEF1F5),
      appBar: AppBar(
        title: const Text('Notifications'),
        actions: [
          IconButton(
            tooltip: 'Refresh notifications',
            onPressed: _busy ? null : () => _load(_page),
            icon: const Icon(Icons.refresh),
          ),
          IconButton(
            tooltip: 'Enable phone alerts',
            onPressed: _busy || _enablingAlerts
                ? null
                : _enablePhoneAlerts,
            icon: const Icon(Icons.notifications_active_outlined),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          if (_loading) ...[
            const LinearProgressIndicator(),
            const SizedBox(height: 16),
          ],
          if (_error != null) ...[
            Text(
              'Could not refresh: $_error',
              style: const TextStyle(color: Colors.red),
            ),
            TextButton(
              onPressed: _busy ? null : () => _load(_page),
              child: const Text('Try again'),
            ),
            const SizedBox(height: 12),
          ],
          if (!_loading && _error == null && _items.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 48),
              child: Column(
                children: [
                  Icon(
                    Icons.notifications_none,
                    size: 42,
                    color: _green,
                  ),
                  SizedBox(height: 14),
                  Text(
                    'You’re all caught up',
                    style: TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  SizedBox(height: 8),
                  Text('Your updates will appear here.'),
                ],
              ),
            ),
          ..._items.map(_card),
          if (_page > 0 || _hasMore)
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                OutlinedButton(
                  onPressed: !_busy && _page > 0
                      ? () => _load(_page - 1)
                      : null,
                  child: const Text('Previous'),
                ),
                Text('Page ${_page + 1}'),
                OutlinedButton(
                  onPressed: !_busy && _hasMore
                      ? () => _load(_page + 1)
                      : null,
                  child: const Text('Next'),
                ),
              ],
            ),
        ],
      ),
    );
  }
}