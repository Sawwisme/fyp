import 'package:flutter/material.dart';

import '../services/checkout_service.dart';

class ShopOrderDetailsScreen extends StatefulWidget {
  final CheckoutService service;
  final int orderId;

  const ShopOrderDetailsScreen({
    super.key,
    required this.service,
    required this.orderId,
  });

  @override
  State<ShopOrderDetailsScreen> createState() =>
      _ShopOrderDetailsScreenState();
}

class _ShopOrderDetailsScreenState
    extends State<ShopOrderDetailsScreen> {
  static const _green = Color(0xFF176B32);

  Map<String, dynamic>? _order;
  String? _error;
  bool _loading = false;
  bool _cancelling = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  String _money(dynamic value) {
    final amount = num.tryParse(value?.toString() ?? '');
    return amount == null
        ? '—'
        : 'RM ${amount.toStringAsFixed(2)}';
  }

  String _date(dynamic value) {
    final parsed = DateTime.tryParse(value?.toString() ?? '');
    if (parsed == null) return '—';

    final date = parsed.toUtc().add(const Duration(hours: 8));
    String two(int value) => value.toString().padLeft(2, '0');

    return '${two(date.day)}/${two(date.month)}/${date.year} '
        '${two(date.hour)}:${two(date.minute)} MYT';
  }

  String _label(dynamic value) {
    final text = value?.toString() ?? 'Unknown';
    return text
        .split('_')
        .map((word) => word.isEmpty
        ? word
        : '${word[0].toUpperCase()}${word.substring(1)}')
        .join(' ');
  }

  Future<void> _load() async {
    if (_loading) return;

    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final order = await widget.service.getOrder(widget.orderId);
      if (!mounted) return;
      setState(() => _order = order);
    } catch (error) {
      if (mounted) {
        setState(() => _error = error.toString());
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _cancel() async {
    if (_cancelling || _loading) return;

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Cancel order?'),
        content: const Text(
          'This will cancel your unpaid order and release its reserved stock.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Keep order'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Cancel order'),
          ),
        ],
      ),
    );

    if (confirmed != true || !mounted) return;

    setState(() => _cancelling = true);

    String? failure;

    try {
      await widget.service.cancelOrder(widget.orderId);
    } catch (error) {
      failure = error.toString();
    }

    // Read the saved state even if the cancellation response was lost.
    await _load();

    if (!mounted) return;

    setState(() => _cancelling = false);

    if (failure != null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            'Cancellation could not be confirmed: $failure',
          ),
        ),
      );
    }
  }

  Widget _panel(List<Widget> children) {
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFFDDE7DF)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: children,
      ),
    );
  }

  Widget _amount(String label, dynamic value, {bool total = false}) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 7),
      child: Row(
        children: [
          Expanded(child: Text(label)),
          Text(
            _money(value),
            style: TextStyle(
              color: total ? _green : null,
              fontSize: total ? 21 : 15,
              fontWeight: total ? FontWeight.bold : FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }

  Widget _body() {
    if (_order == null) {
      if (_loading) {
        return const Center(child: CircularProgressIndicator());
      }

      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(_error ?? 'Order unavailable.'),
              const SizedBox(height: 12),
              OutlinedButton(
                onPressed: _load,
                child: const Text('Try again'),
              ),
            ],
          ),
        ),
      );
    }

    final order = _order!;
    final pending = order['order_status'] == 'pending_payment';
    final busy = _loading || _cancelling;

    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        if (_loading) const LinearProgressIndicator(),
        if (_error != null)
          Padding(
            padding: const EdgeInsets.only(bottom: 16),
            child: Text(
              'Could not refresh: $_error',
              style: const TextStyle(color: Colors.red),
            ),
          ),
        _panel([
          Text(
            order['clinic_name'].toString(),
            style: const TextStyle(
              fontSize: 21,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 8),
          Text('Order #${order['order_id']}'),
          const SizedBox(height: 14),
          Container(
            padding: const EdgeInsets.symmetric(
              horizontal: 12,
              vertical: 7,
            ),
            decoration: BoxDecoration(
              color: const Color(0xFFE8F3EB),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Text(
              _label(order['order_status']),
              style: const TextStyle(
                color: _green,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
          const SizedBox(height: 12),
          Text('Payment: ${_label(order['payment_status'])}'),
          Text('Placed: ${_date(order['order_date'])}'),
          if (pending) ...[
            const SizedBox(height: 12),
            Text(
              'Payment deadline: '
                  '${_date(order['payment_expires_at'])}',
            ),
            const SizedBox(height: 8),
            const Text(
              'Unpaid orders expire automatically. '
                  'Online banking will be available after payment integration.',
              style: TextStyle(color: Colors.black54),
            ),
          ],
        ]),
        _panel([
          Text(
            order['shipping_method'] == 'pickup'
                ? 'Clinic pickup'
                : 'Delivery',
            style: const TextStyle(
              fontSize: 17,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 12),
          Text(order['recipient_name'].toString()),
          Text(order['recipient_phone'].toString()),
          const SizedBox(height: 10),
          Text(order['shipping_address'].toString()),
          if ((order['owner_note']?.toString() ?? '').isNotEmpty) ...[
            const Divider(height: 28),
            Text('Note: ${order['owner_note']}'),
          ],
        ]),
        _panel([
          const Text(
            'Order summary',
            style: TextStyle(
              fontSize: 17,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 14),
          ...(order['items'] as List).map((entry) {
            final item = Map<String, dynamic>.from(entry as Map);

            return Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: Text(
                      '${item['product_name']} × ${item['quantity']}',
                    ),
                  ),
                  const SizedBox(width: 12),
                  Text(_money(item['subtotal'])),
                ],
              ),
            );
          }),
          const Divider(),
          _amount('Subtotal', order['subtotal']),
          _amount('Delivery / pickup fee', order['shipping_fee']),
          const Divider(),
          _amount('Total', order['total_amount'], total: true),
        ]),
        if (pending)
          OutlinedButton(
            onPressed: busy || _error != null ? null : _cancel,
            style: OutlinedButton.styleFrom(
              foregroundColor: Colors.red.shade700,
              padding: const EdgeInsets.symmetric(vertical: 14),
            ),
            child: Text(
              _cancelling ? 'Cancelling…' : 'Cancel unpaid order',
            ),
          ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: !_cancelling,
      child: Scaffold(
        backgroundColor: const Color(0xFFF5F7F5),
        appBar: AppBar(
          title: Text('Order #${widget.orderId}'),
          actions: [
            IconButton(
              tooltip: 'Refresh order',
              onPressed: _loading || _cancelling ? null : _load,
              icon: const Icon(Icons.refresh),
            ),
          ],
        ),
        body: _body(),
      ),
    );
  }
}