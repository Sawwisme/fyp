import 'package:flutter/material.dart';

import '../services/api_client.dart';
import '../services/cart_service.dart';
import '../services/checkout_service.dart';
import 'cart.dart';
import 'checkout.dart';

class ChatProductCard extends StatefulWidget {
  final CartService service;
  final Map<String, dynamic> product;
  final bool enabled;

  const ChatProductCard({
    super.key,
    required this.service,
    required this.product,
    required this.enabled,
  });

  @override
  State<ChatProductCard> createState() => _ChatProductCardState();
}

class _ChatProductCardState extends State<ChatProductCard> {
  bool _busy = false;
  bool _uncertain = false;
  String? _message;

  Future<void> _add({required bool checkout}) async {
    if (_busy || _uncertain || !widget.enabled) return;

    setState(() {
      _busy = true;
      _message = null;
    });

    var added = false;

    try {
      await widget.service.addProduct(
        clinicId: widget.product['clinic_id'] as int,
        productId: widget.product['product_id'] as int,
      );

      added = true;

      if (!mounted) return;

      setState(() {
        _message = 'One item added to your clinic cart.';
      });

      if (checkout) {
        await Navigator.of(context).push<void>(
          MaterialPageRoute(
            builder: (_) => CheckoutScreen(
              service: CheckoutService(widget.service.api),
              clinicId: widget.product['clinic_id'] as int,
            ),
          ),
        );
      }
    } catch (error) {
      if (!mounted) return;

      final status = error is ApiException ? error.statusCode : null;

      final uncertain = !added &&
          (status == null ||
              status >= 500 ||
              (status >= 200 && status < 300));

      setState(() {
        _uncertain = uncertain;

        _message = uncertain
            ? 'The cart update could not be confirmed. Open your cart '
            'and check the quantity before making another change.'
            : added
            ? 'Item added. Open your cart to continue checkout.'
            : error.toString();
      });
    } finally {
      if (mounted) {
        setState(() => _busy = false);
      }
    }
  }

  Future<void> _openCart() async {
    if (_busy || !widget.enabled) return;

    setState(() => _busy = true);

    try {
      await Navigator.of(context).push<void>(
        MaterialPageRoute(
          builder: (_) => CartScreen(
            service: widget.service,
            clinicId: widget.product['clinic_id'] as int,
          ),
        ),
      );
    } finally {
      if (mounted) {
        setState(() => _busy = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final price = num.tryParse('${widget.product['price']}');
    final canAdd = widget.enabled && !_busy && !_uncertain;

    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(top: 12),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFFF4F6FC),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFFDCE2ED)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '${widget.product['product_name']}',
            style: const TextStyle(fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 4),
          Text('${widget.product['clinic_name']}'),
          const SizedBox(height: 6),
          Text(
            price == null
                ? 'Check price at checkout'
                : 'RM ${price.toStringAsFixed(2)}',
          ),
          const SizedBox(height: 10),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              OutlinedButton(
                onPressed: canAdd ? () => _add(checkout: false) : null,
                child: const Text('Add to cart'),
              ),
              FilledButton(
                onPressed: canAdd ? () => _add(checkout: true) : null,
                child: Text(_busy ? 'Please wait…' : 'Buy now'),
              ),
              TextButton(
                onPressed: widget.enabled && !_busy ? _openCart : null,
                child: const Text('View cart'),
              ),
            ],
          ),
          const SizedBox(height: 6),
          const Text(
            'Buy now adds one item and opens this clinic’s cart checkout. '
                'Existing cart items are included. Price and stock are rechecked.',
            style: TextStyle(
              fontSize: 12,
              color: Color(0xFF53627A),
            ),
          ),
          if (_message != null) ...[
            const SizedBox(height: 8),
            Text(_message!),
          ],
        ],
      ),
    );
  }
}