import 'package:flutter/material.dart';

import '../services/checkout_service.dart';
import 'shop_order_details.dart';

class ShopOrdersScreen extends StatefulWidget {
  final CheckoutService service;

  const ShopOrdersScreen({
    super.key,
    required this.service,
  });

  @override
  State<ShopOrdersScreen> createState() => _ShopOrdersScreenState();
}

class _ShopOrdersScreenState extends State<ShopOrdersScreen> {
  static const _green = Color(0xFF176B32);
  static const _pageSize = 10;

  late Future<List<Map<String, dynamic>>> _future;
  int _page = 0;

  @override
  void initState() {
    super.initState();
    _future = _fetch();
  }

  Future<List<Map<String, dynamic>>> _fetch() {
    return widget.service.getOrders(
      offset: _page * _pageSize,
      limit: _pageSize + 1,
    );
  }

  void _load([int? page]) {
    setState(() {
      _page = page ?? _page;
      _future = _fetch();
    });
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

    return '${two(date.day)}/${two(date.month)}/${date.year}';
  }

  String _label(dynamic value) {
    return (value?.toString() ?? 'Unknown')
        .split('_')
        .map(
          (word) => word.isEmpty
          ? word
          : '${word[0].toUpperCase()}${word.substring(1)}',
    )
        .join(' ');
  }

  Color _statusColor(String status) {
    switch (status) {
      case 'pending_payment':
        return const Color(0xFF946200);
      case 'cancelled':
      case 'expired':
        return const Color(0xFF66716A);
      default:
        return _green;
    }
  }

  Future<void> _openOrder(Map<String, dynamic> order) async {
    await Navigator.of(context).push<void>(
      MaterialPageRoute(
        builder: (_) => ShopOrderDetailsScreen(
          service: widget.service,
          orderId: order['order_id'] as int,
        ),
      ),
    );

    // Cancellation or payment may have changed the order.
    if (mounted) _load();
  }

  Widget _orderCard(Map<String, dynamic> order) {
    final status = order['order_status'].toString();
    final color = _statusColor(status);
    final items = order['items'] as List;
    final quantity = items.fold<int>(
      0,
          (total, entry) =>
      total + ((entry as Map)['quantity'] as int),
    );

    return Card(
      color: Colors.white,
      elevation: 0,
      margin: const EdgeInsets.only(bottom: 14),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(14),
        side: const BorderSide(color: Color(0xFFDDE7DF)),
      ),
      child: InkWell(
        onTap: () => _openOrder(order),
        borderRadius: BorderRadius.circular(14),
        child: Padding(
          padding: const EdgeInsets.all(18),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: Text(
                      'Order #${order['order_id']}',
                      style: const TextStyle(
                        fontSize: 17,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Align(
                      alignment: Alignment.topRight,
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 10,
                          vertical: 6,
                        ),
                        decoration: BoxDecoration(
                          color: color.withValues(alpha: 0.09),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Text(
                          _label(status),
                          textAlign: TextAlign.right,
                          style: TextStyle(
                            color: color,
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 14),
              Text(
                order['clinic_name'].toString(),
                style: const TextStyle(
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: 6),
              Text(
                '${_date(order['order_date'])} · '
                    '${order['shipping_method'] == 'pickup' ? 'Clinic pickup' : 'Delivery'}',
                style: const TextStyle(
                  color: Colors.black54,
                  fontSize: 13,
                ),
              ),
              const SizedBox(height: 14),
              Row(
                children: [
                  Expanded(
                    child: Text(
                      '$quantity ${quantity == 1 ? 'item' : 'items'}',
                      style: const TextStyle(color: Colors.black54),
                    ),
                  ),
                  Text(
                    _money(order['total_amount']),
                    style: const TextStyle(
                      color: _green,
                      fontSize: 19,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ],
              ),
              const Divider(height: 28),
              const Row(
                children: [
                  Expanded(
                    child: Text(
                      'View order details',
                      style: TextStyle(
                        color: _green,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                  Icon(Icons.chevron_right, color: _green),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF5F7F5),
      appBar: AppBar(
        title: const Text('My Orders'),
        actions: [
          IconButton(
            tooltip: 'Refresh orders',
            onPressed: () => _load(0),
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: FutureBuilder<List<Map<String, dynamic>>>(
        future: _future,
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }

          if (snapshot.hasError) {
            return Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      snapshot.error.toString(),
                      textAlign: TextAlign.center,
                    ),
                    const SizedBox(height: 12),
                    OutlinedButton(
                      onPressed: () => _load(),
                      child: const Text('Try again'),
                    ),
                  ],
                ),
              ),
            );
          }

          final orders = snapshot.data ?? [];
          final hasMore = orders.length > _pageSize;

          return RefreshIndicator(
            onRefresh: () async {
              _load(0);
              await _future;
            },
            child: ListView(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.all(20),
              children: [
                if (orders.isEmpty)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 60),
                    child: Column(
                      children: [
                        const Icon(
                          Icons.receipt_long_outlined,
                          size: 48,
                          color: _green,
                        ),
                        const SizedBox(height: 16),
                        Text(
                          _page == 0
                              ? 'No orders yet'
                              : 'No orders on this page',
                          style: const TextStyle(
                            fontSize: 19,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(height: 8),
                        const Text(
                          'Your clinic shop orders will appear here.',
                          textAlign: TextAlign.center,
                          style: TextStyle(color: Colors.black54),
                        ),
                      ],
                    ),
                  ),
                ...orders.take(_pageSize).map(_orderCard),
                if (_page > 0 || hasMore)
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      OutlinedButton(
                        onPressed: _page > 0
                            ? () => _load(_page - 1)
                            : null,
                        child: const Text('Previous'),
                      ),
                      Text('Page ${_page + 1}'),
                      OutlinedButton(
                        onPressed: hasMore
                            ? () => _load(_page + 1)
                            : null,
                        child: const Text('Next'),
                      ),
                    ],
                  ),
              ],
            ),
          );
        },
      ),
    );
  }
}