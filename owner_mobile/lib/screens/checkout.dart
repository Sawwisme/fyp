import 'package:flutter/material.dart';

import '../services/api_client.dart';
import '../services/checkout_service.dart';

class CheckoutScreen extends StatefulWidget {
  final CheckoutService service;
  final int clinicId;

  const CheckoutScreen({
    super.key,
    required this.service,
    required this.clinicId,
  });

  @override
  State<CheckoutScreen> createState() => _CheckoutScreenState();
}

class _CheckoutScreenState extends State<CheckoutScreen> {
  static const _green = Color(0xFF176B32);

  Map<String, dynamic>? _cart;
  Map<String, dynamic>? _settings;
  Map<String, dynamic>? _quote;

  String? _method;
  String? _error;
  String? _quoteError;

  bool _loading = true;
  bool _quoting = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  String _money(dynamic value) {
    final amount = num.tryParse(value?.toString() ?? '');
    return amount == null ? '—' : 'RM ${amount.toStringAsFixed(2)}';
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
      _quote = null;
    });

    try {
      final results = await Future.wait([
        widget.service.getCart(widget.clinicId),
        widget.service.getSettings(widget.clinicId),
      ]);

      if (!mounted) return;

      _cart = results[0];
      _settings = results[1];

      if (_settings!['pickup_enabled'] != true &&
          _settings!['delivery_enabled'] != true) {
        throw const ApiException(
          'This clinic has no available collection or delivery method.',
        );
      }

      _method = _settings!['pickup_enabled'] == true
          ? 'pickup'
          : 'delivery';

      await _loadQuote(_method!);
    } catch (error) {
      if (mounted) {
        setState(() => _error = error.toString());
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _loadQuote(String method) async {
    setState(() {
      _method = method;
      _quoting = true;
      _quote = null;
      _quoteError = null;
    });

    try {
      final quote = await widget.service.getQuote(
        clinicId: widget.clinicId,
        cartVersion: _cart!['version'] as int,
        shippingMethod: method,
      );

      if (!mounted) return;
      setState(() => _quote = quote);
    } catch (error) {
      if (mounted) {
        setState(() => _quoteError = error.toString());
      }
    } finally {
      if (mounted) setState(() => _quoting = false);
    }
  }

  Widget _amountRow(
      String label,
      dynamic amount, {
        bool total = false,
      }) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        children: [
          Expanded(
            child: Text(
              label,
              style: TextStyle(
                fontWeight: total ? FontWeight.bold : FontWeight.normal,
              ),
            ),
          ),
          Text(
            _money(amount),
            style: TextStyle(
              color: total ? _green : null,
              fontSize: total ? 22 : 15,
              fontWeight: total ? FontWeight.bold : FontWeight.normal,
            ),
          ),
        ],
      ),
    );
  }

  Widget _panel(Widget child) {
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFFDDE7DF)),
      ),
      child: child,
    );
  }

  Widget _body() {
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_error != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(_error!, textAlign: TextAlign.center),
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

    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        Text(
          _cart!['clinic_name'].toString(),
          style: const TextStyle(
            fontSize: 21,
            fontWeight: FontWeight.bold,
          ),
        ),
        const SizedBox(height: 18),
        _panel(
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Receive your order',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: 14),
              DropdownButtonFormField<String>(
                key: ValueKey(_method),
                initialValue: _method,
                isExpanded: true,
                decoration: const InputDecoration(
                  labelText: 'Method',
                  border: OutlineInputBorder(),
                ),
                items: [
                  if (_settings!['pickup_enabled'] == true)
                    const DropdownMenuItem(
                      value: 'pickup',
                      child: Text('Clinic pickup'),
                    ),
                  if (_settings!['delivery_enabled'] == true)
                    const DropdownMenuItem(
                      value: 'delivery',
                      child: Text('Delivery'),
                    ),
                ],
                onChanged: _quoting
                    ? null
                    : (value) {
                  if (value != null) _loadQuote(value);
                },
              ),
              if (_method == 'pickup' &&
                  _quote?['pickup_address'] != null) ...[
                const SizedBox(height: 14),
                const Text(
                  'Pickup address',
                  style: TextStyle(fontWeight: FontWeight.w600),
                ),
                const SizedBox(height: 6),
                Text(_quote!['pickup_address'].toString()),
              ],
            ],
          ),
        ),
        if (_quoting)
          const Padding(
            padding: EdgeInsets.all(20),
            child: Center(child: CircularProgressIndicator()),
          ),
        if (_quoteError != null)
          _panel(
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  _quoteError!,
                  style: const TextStyle(color: Colors.red),
                ),
                TextButton(
                  onPressed: _quoting ? null : _load,
                  child: const Text('Reload checkout'),
                ),
              ],
            ),
          ),
        if (_quote != null)
          _panel(
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Order summary',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 12),
                ...(_quote!['items'] as List).map((entry) {
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
                        Text(_money(item['line_total'])),
                      ],
                    ),
                  );
                }),
                const Divider(),
                _amountRow('Subtotal', _quote!['subtotal']),
                _amountRow(
                  _method == 'pickup' ? 'Pickup fee' : 'Delivery fee',
                  _quote!['shipping_fee'],
                ),
                const Divider(),
                _amountRow(
                  'Total',
                  _quote!['total_amount'],
                  total: true,
                ),
              ],
            ),
          ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF5F7F5),
      appBar: AppBar(title: const Text('Checkout')),
      body: _body(),
    );
  }
}