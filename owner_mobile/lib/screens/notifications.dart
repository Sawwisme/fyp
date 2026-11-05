import 'package:flutter/material.dart';

import '../services/checkout_service.dart';
import '../services/notification_service.dart';
import 'shop_order_details.dart';
import '../services/billing_service.dart';
import 'bill_details.dart';

class OwnerNotificationsScreen extends StatefulWidget {
  final NotificationService service;

  const OwnerNotificationsScreen({
    super.key,
    required this.service,
  });

  @override
  State<OwnerNotificationsScreen> createState() =>
      _OwnerNotificationsScreenState();
}

class _OwnerNotificationsScreenState
    extends State<OwnerNotificationsScreen> {
  static const _green = Color(0xFF176B32);
  static const _pageSize = 20;

  List<Map<String, dynamic>> _items = [];
  int _page = 0;
  bool _hasMore = false;
  bool _loading = false;
  int? _readingId;
  String? _error;

  bool get _busy => _loading || _readingId != null;

  @override
  void initState() {
    super.initState();
    _load();
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

  Widget _card(Map<String, dynamic> item) {
    final unread = item['read_at'] == null;
    final shopOrder = item['resource_type'] == 'shop_order';
    final consultationBill =
        item['resource_type'] == 'consultation_bill';
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
          if (shopOrder || consultationBill || unread) ...[
            const SizedBox(height: 12),
            Wrap(
              spacing: 10,
              runSpacing: 8,
              children: [
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
      backgroundColor: const Color(0xFFF5F7F5),
      appBar: AppBar(
        title: const Text('Notifications'),
        actions: [
          IconButton(
            tooltip: 'Refresh notifications',
            onPressed: _busy ? null : () => _load(_page),
            icon: const Icon(Icons.refresh),
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