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
  int _quantity = 1;

  Future<void> _add({required bool checkout}) async {
    if (_busy || _uncertain || !widget.enabled) return;

    setState(() {
      _busy = true;
      _message = null;
    });

    var added = false;

    try {
      final clinicId = widget.product['clinic_id'] as int;
      final productId = widget.product['product_id'] as int;

// Read the current cart so existing quantities are preserved.
      final cart = await widget.service.getCart(clinicId);

      var existingQuantity = 0;

      for (final entry in cart['items'] as List) {
        final item = Map<String, dynamic>.from(entry as Map);

        if (item['product_id'] == productId) {
          existingQuantity = item['quantity'] as int;
          break;
        }
      }

      final requestedQuantity = existingQuantity + _quantity;

      if (requestedQuantity > 99) {
        throw const ApiException(
          'The cart can contain up to 99 units of one product.',
          statusCode: 422,
        );
      }

      await widget.service.setQuantity(
        clinicId: clinicId,
        productId: productId,
        expectedVersion: cart['version'] as int,
        quantity: requestedQuantity,
      );

      added = true;

      if (!mounted) return;

      setState(() {
        _message = '$_quantity '
            '${_quantity == 1 ? 'item' : 'items'} added to your clinic cart.';
      });

      if (checkout) {
        await Navigator.of(context).push<void>(
          MaterialPageRoute(
            builder: (_) => CheckoutScreen(
              service: CheckoutService(widget.service.api),
              clinicId: clinicId,
              selectedProductIds: [productId],
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
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Icon(
                Icons.storefront_outlined,
                size: 16,
                color: Color(0xFF63718A),
              ),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  '${widget.product['clinic_name']}',
                  style: const TextStyle(
                    color: Color(0xFF63718A),
                  ),
                ),
              ),
            ],
          ),
          if ((widget.product['clinic_state'] ?? '')
              .toString()
              .trim()
              .isNotEmpty) ...[
            const SizedBox(height: 4),
            Text(
              '${widget.product['clinic_state']}',
              style: const TextStyle(
                fontSize: 12,
                color: Color(0xFF63718A),
              ),
            ),
          ],
          const SizedBox(height: 8),
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: [
              if (widget.product['shop_pickup_enabled'] == true)
                const Chip(
                  avatar: Icon(
                    Icons.store_outlined,
                    size: 16,
                  ),
                  label: Text('Clinic pickup'),
                  visualDensity: VisualDensity.compact,
                ),
              if (widget.product['shop_delivery_enabled'] == true)
                const Chip(
                  avatar: Icon(
                    Icons.local_shipping_outlined,
                    size: 16,
                  ),
                  label: Text('Delivery available'),
                  visualDensity: VisualDensity.compact,
                ),
            ],
          ),
          const SizedBox(height: 4),
          const Text(
            'Confirm current fulfilment options and any delivery '
                'charges at checkout.',
            style: TextStyle(
              fontSize: 11,
              color: Color(0xFF63718A),
            ),
          ),
          const SizedBox(height: 10),
          Text(
            price == null
                ? 'Check price at checkout'
                : 'RM ${price.toStringAsFixed(2)}',
          ),
          const SizedBox(height: 10),
          if ((widget.product['recommendation_reason'] ?? '')
              .toString()
              .trim()
              .isNotEmpty) ...[
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: const Color(0xFFEAF0FF),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Why this matches',
                    style: TextStyle(
                      color: Color(0xFF2549C7),
                      fontWeight: FontWeight.w700,
                      fontSize: 12,
                    ),
                  ),
                  const SizedBox(height: 5),
                  Text(
                    '${widget.product['recommendation_reason']}',
                    style: const TextStyle(fontSize: 12, height: 1.5),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 10),
          ],

          if ((widget.product['suitability_notes'] ?? '')
              .toString()
              .trim()
              .isNotEmpty) ...[
            Text(
              'Label notes: ${widget.product['suitability_notes']}',
              style: const TextStyle(
                fontSize: 12,
                color: Color(0xFF53627A),
              ),
            ),
            const SizedBox(height: 10),
          ],

          DropdownButtonFormField<int>(
            initialValue: _quantity,
            decoration: const InputDecoration(
              labelText: 'Quantity to add',
              border: OutlineInputBorder(),
              isDense: true,
            ),
            items: [
              for (var value = 1; value <= 10; value++)
                DropdownMenuItem(
                  value: value,
                  child: Text('$value'),
                ),
            ],
            onChanged: canAdd
                ? (value) {
              if (value == null) return;
              setState(() => _quantity = value);
            }
                : null,
          ),
          const SizedBox(height: 12),
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
            'Buy now adds the selected quantity and opens checkout. '
                'Existing items in this clinic’s cart are included. '
                'Price and stock are checked again.',
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