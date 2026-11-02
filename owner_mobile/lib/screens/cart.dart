import 'package:flutter/material.dart';

import '../services/cart_service.dart';
import '../services/checkout_service.dart';
import 'checkout.dart';

class CartScreen extends StatefulWidget {
  final CartService service;
  final int clinicId;

  const CartScreen({
    super.key,
    required this.service,
    required this.clinicId,
  });

  @override
  State<CartScreen> createState() => _CartScreenState();
}

class _CartScreenState extends State<CartScreen> {
  static const _green = Color(0xFF176B32);

  Map<String, dynamic>? _cart;
  String? _error;
  bool _loading = true;
  bool _saving = false;

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
    if (_saving) return;

    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final cart = await widget.service.getCart(widget.clinicId);
      if (!mounted) return;
      setState(() => _cart = cart);
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _cart = null;
        _error = error.toString();
      });
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _change(
      Map<String, dynamic> item,
      int quantity,
      ) async {
    if (_saving || _cart == null) return;

    setState(() => _saving = true);

    try {
      final cart = await widget.service.setQuantity(
        clinicId: widget.clinicId,
        productId: item['product_id'] as int,
        expectedVersion: _cart!['version'] as int,
        quantity: quantity,
      );

      if (!mounted) return;
      setState(() => _cart = cart);
    } catch (error) {
      // Read the actual cart instead of repeating an uncertain update.
      try {
        final latest = await widget.service.getCart(widget.clinicId);
        if (!mounted) return;
        setState(() => _cart = latest);
      } catch (_) {
        if (!mounted) return;
        setState(() {
          _cart = null;
          _error = 'Unable to reload your cart. Please try again.';
        });
      }

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(error.toString())),
        );
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _openCheckout() async {
    if (_saving || _cart?['can_checkout'] != true) return;

    await Navigator.of(context).push<void>(
      MaterialPageRoute(
        builder: (_) => CheckoutScreen(
          service: CheckoutService(widget.service.api),
          clinicId: widget.clinicId,
        ),
      ),
    );

    if (mounted) await _load();
  }

  Widget _itemCard(Map<String, dynamic> item) {
    final quantity = item['quantity'] as int;
    final stock = item['stock_quantity'] as int;
    final available = item['available'] == true;

    return Card(
      elevation: 0,
      color: Colors.white,
      margin: const EdgeInsets.only(bottom: 12),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(14),
        side: const BorderSide(color: Color(0xFFDDE7DF)),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              item['product_name'].toString(),
              style: const TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              '${_money(item['unit_price'])} each',
              style: const TextStyle(color: _green),
            ),
            if (!available) ...[
              const SizedBox(height: 8),
              Text(
                'Unavailable in the requested quantity. '
                    'Remove this item before checkout.',
                style: TextStyle(color: Colors.red.shade700),
              ),
            ],
            if (item['price_changed'] == true) ...[
              const SizedBox(height: 8),
              const Text(
                'Price changed. The current price is shown.',
                style: TextStyle(color: Color(0xFF9A6016)),
              ),
            ],
            const SizedBox(height: 12),
            Row(
              children: [
                if (available) ...[
                  IconButton.outlined(
                    tooltip: 'Decrease quantity',
                    onPressed: !_saving && quantity > 1
                        ? () => _change(item, quantity - 1)
                        : null,
                    icon: const Icon(Icons.remove),
                  ),
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 14),
                    child: Text('$quantity'),
                  ),
                  IconButton.outlined(
                    tooltip: 'Increase quantity',
                    onPressed: !_saving && quantity < stock && quantity < 99
                        ? () => _change(item, quantity + 1)
                        : null,
                    icon: const Icon(Icons.add),
                  ),
                ] else
                  Text('Quantity: $quantity'),
                const Spacer(),
                IconButton(
                  tooltip: 'Remove item',
                  onPressed: _saving ? null : () => _change(item, 0),
                  icon: const Icon(Icons.delete_outline),
                ),
              ],
            ),
            Align(
              alignment: Alignment.centerRight,
              child: Text(
                _money(item['line_total']),
                style: const TextStyle(fontWeight: FontWeight.bold),
              ),
            ),
          ],
        ),
      ),
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

    final cart = _cart!;
    final items = (cart['items'] as List)
        .map((item) => Map<String, dynamic>.from(item as Map))
        .toList();

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(20),
        children: [
          Text(
            cart['clinic_name'].toString(),
            style: const TextStyle(
              fontSize: 20,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 16),
          if (items.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 40),
              child: Text(
                'Your cart is empty.',
                textAlign: TextAlign.center,
              ),
            ),
          ...items.map(_itemCard),
          if (items.isNotEmpty) ...[
            const SizedBox(height: 12),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text('Subtotal'),
                Text(
                  _money(cart['subtotal']),
                  style: const TextStyle(
                    color: _green,
                    fontSize: 21,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            const Text(
              'Delivery charges will be calculated at checkout.',
              style: TextStyle(color: Colors.grey, fontSize: 12),
            ),
          ],
          if (items.isNotEmpty) ...[
            const SizedBox(height: 20),
            FilledButton(
              onPressed: !_saving && cart['can_checkout'] == true
                  ? _openCheckout
                  : null,
              child: const Text('Continue to checkout'),
            ),
          ],
          if (_saving) ...[
            const SizedBox(height: 16),
            const LinearProgressIndicator(),
          ],
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: !_saving,
      child: Scaffold(
        backgroundColor: const Color(0xFFF5F7F5),
        appBar: AppBar(title: const Text('My Cart')),
        body: _body(),
      ),
    );
  }
}