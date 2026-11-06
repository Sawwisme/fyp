import 'package:flutter/material.dart';

import '../services/api_client.dart';
import '../services/checkout_service.dart';
import 'dart:math';

import 'shop_order_details.dart';

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
  String _paymentMethod = 'online_banking';
  String? _error;
  String? _quoteError;

  bool _loading = true;
  bool _quoting = false;

  final _formKey = GlobalKey<FormState>();

  final _nameController = TextEditingController();
  final _phoneController = TextEditingController();
  final _addressController = TextEditingController();
  final _noteController = TextEditingController();

  Map<String, dynamic>? _pendingOrder;

  bool _placing = false;
  bool _uncertain = false;
  String? _orderError;

  @override
  void dispose() {
    _nameController.dispose();
    _phoneController.dispose();
    _addressController.dispose();
    _noteController.dispose();
    super.dispose();
  }

  String _newCheckoutKey() {
    final random = Random.secure();
    final bytes = List<int>.generate(16, (_) => random.nextInt(256));

    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;

    final hex = bytes
        .map((value) => value.toRadixString(16).padLeft(2, '0'))
        .join();

    return '${hex.substring(0, 8)}-'
        '${hex.substring(8, 12)}-'
        '${hex.substring(12, 16)}-'
        '${hex.substring(16, 20)}-'
        '${hex.substring(20)}';
  }

  Future<void> _placeOrder() async {
    if (_placing || _quoting || _loading || _quote == null) return;

    if (_pendingOrder == null) {
      if (!(_formKey.currentState?.validate() ?? false)) return;

      FocusScope.of(context).unfocus();

      _pendingOrder = {
        'checkout_key': _newCheckoutKey(),
        'expected_cart_version': _quote!['cart_version'],
        'expected_settings_version': _quote!['settings_version'],
        'expected_total_amount': _quote!['total_amount'].toString(),
        'shipping_method': _method,
        'payment_method': _paymentMethod,
        'recipient_name': _nameController.text.trim(),
        'recipient_phone': _phoneController.text.trim(),
        if (_method == 'delivery')
          'delivery_address': _addressController.text.trim(),
        'owner_note': _noteController.text.trim().isEmpty
            ? null
            : _noteController.text.trim(),
      };
    }

    setState(() {
      _placing = true;
      _orderError = null;
    });

    try {
      // Retrying keeps the original key and exact payload.
      final order = await widget.service.createOrder(
        clinicId: widget.clinicId,
        payload: Map<String, dynamic>.from(_pendingOrder!),
      );

      if (!mounted) return;

      setState(() {
        _placing = false;
        _pendingOrder = null;
        _uncertain = false;
      });

      Navigator.of(context).pushReplacement(
        MaterialPageRoute(
          builder: (_) => ShopOrderDetailsScreen(
            service: widget.service,
            orderId: order['order_id'] as int,
          ),
        ),
      );
    } catch (error) {
      if (!mounted) return;

      final code = error is ApiException ? error.statusCode : null;

      final uncertainResponse = code == null ||
          code >= 500 ||
          code < 300 ||
          code == 408 ||
          code == 429;

      setState(() {
        _placing = false;
        _uncertain = _uncertain || uncertainResponse;

        if (_uncertain) {
          _orderError =
          'The order could not be confirmed. Tap Retry order '
              'to check or submit the same order safely.';
        } else {
          // A definite rejection allows editing and a fresh quote.
          _pendingOrder = null;
          _orderError = error.toString();
          _quote = null;
          _quoteError =
          'Reload checkout and review the latest stock and total.';
        }
      });
    }
  }

  Widget _paymentOptions() {
    final locked = _placing ||
        _quoting ||
        _pendingOrder != null;

    return _panel(
      Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Payment method',
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 14),
          DropdownButtonFormField<String>(
            key: ValueKey('payment-$_method-$_paymentMethod'),
            initialValue: _paymentMethod,
            isExpanded: true,
            decoration: const InputDecoration(
              labelText: 'How would you like to pay?',
              border: OutlineInputBorder(),
            ),
            items: [
              const DropdownMenuItem(
                value: 'online_banking',
                child: Text('Online banking'),
              ),
              if (_method == 'pickup')
                const DropdownMenuItem(
                  value: 'cash',
                  child: Text('Cash at clinic pickup'),
                ),
            ],
            onChanged: locked
                ? null
                : (value) {
              if (value == null) return;

              setState(() => _paymentMethod = value);
            },
          ),
          const SizedBox(height: 12),
          Text(
            _paymentMethod == 'cash'
                ? 'Pay the clinic when collecting your order.'
                : _method == 'delivery'
                ? 'Delivery orders require online payment.'
                : 'Pay online after placing your order.',
            style: const TextStyle(
              color: Colors.black54,
              height: 1.5,
            ),
          ),
        ],
      ),
    );
  }

  Widget _recipientForm() {
    final locked = _placing || _pendingOrder != null;

    return _panel(
      Form(
        key: _formKey,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Contact details',
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 14),
            TextFormField(
              controller: _nameController,
              enabled: !locked,
              maxLength: 150,
              textCapitalization: TextCapitalization.words,
              decoration: const InputDecoration(
                labelText: 'Recipient name',
                border: OutlineInputBorder(),
                counterText: '',
              ),
              validator: (value) {
                if ((value?.trim().length ?? 0) < 2) {
                  return 'Enter the recipient’s name.';
                }
                return null;
              },
            ),
            const SizedBox(height: 14),
            TextFormField(
              controller: _phoneController,
              enabled: !locked,
              maxLength: 20,
              keyboardType: TextInputType.phone,
              decoration: const InputDecoration(
                labelText: 'Phone number',
                hintText: 'e.g. +60123456789',
                border: OutlineInputBorder(),
                counterText: '',
              ),
              validator: (value) {
                final phone = value?.trim() ?? '';
                if (!RegExp(
                  r'^\+?[0-9][0-9 ()-]{5,18}[0-9]$',
                ).hasMatch(phone)) {
                  return 'Enter a valid phone number.';
                }
                return null;
              },
            ),
            if (_method == 'delivery') ...[
              const SizedBox(height: 14),
              TextFormField(
                controller: _addressController,
                enabled: !locked,
                maxLength: 500,
                minLines: 3,
                maxLines: 5,
                keyboardType: TextInputType.multiline,
                decoration: const InputDecoration(
                  labelText: 'Full delivery address',
                  hintText: 'Street, city, postcode and state',
                  alignLabelWithHint: true,
                  border: OutlineInputBorder(),
                ),
                validator: (value) {
                  if ((value?.trim().length ?? 0) < 10) {
                    return 'Enter your full delivery address.';
                  }
                  return null;
                },
              ),
            ],
            const SizedBox(height: 14),
            TextFormField(
              controller: _noteController,
              enabled: !locked,
              maxLength: 500,
              minLines: 2,
              maxLines: 4,
              decoration: const InputDecoration(
                labelText: 'Order note (optional)',
                alignLabelWithHint: true,
                border: OutlineInputBorder(),
              ),
            ),
          ],
        ),
      ),
    );
  }

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

      if (method == 'delivery') {
        _paymentMethod = 'online_banking';
      }

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
                onChanged: (_quoting || _placing || _pendingOrder != null)
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
        _paymentOptions(),
        _recipientForm(),

        if (_orderError != null)
          Padding(
            padding: const EdgeInsets.only(bottom: 14),
            child: Text(
              _orderError!,
              style: const TextStyle(color: Colors.red),
            ),
          ),

        FilledButton(
          onPressed: _placing ||
              _quoting ||
              _loading ||
              _quote == null
              ? null
              : _placeOrder,
          style: FilledButton.styleFrom(
            backgroundColor: _green,
            padding: const EdgeInsets.symmetric(vertical: 16),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(10),
            ),
          ),
          child: Text(
            _placing
                ? 'Placing order…'
                : _pendingOrder != null
                ? 'Retry order'
                : 'Place order',
          ),
        ),

        const SizedBox(height: 10),

        Text(
          _paymentMethod == 'cash'
              ? 'Your pickup order will be confirmed. '
              'Payment remains pending until the clinic receives cash.'
              : 'Your order will be pending payment. '
              'Complete online payment within 15 minutes.',
          textAlign: TextAlign.center,
          style: const TextStyle(
            color: Colors.black54,
            fontSize: 13,
          ),
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: !_placing,
      child: Scaffold(
        backgroundColor: const Color(0xFFF5F7F5),
        appBar: AppBar(title: const Text('Checkout')),
        body: _body(),
      ),
    );
  }
}