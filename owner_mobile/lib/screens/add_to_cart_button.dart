import 'package:flutter/material.dart';

import '../services/api_client.dart';
import '../services/cart_service.dart';

class AddToCartButton extends StatefulWidget {
  final CartService service;
  final int clinicId;
  final int productId;
  final bool inStock;

  const AddToCartButton({
    super.key,
    required this.service,
    required this.clinicId,
    required this.productId,
    required this.inStock,
  });

  @override
  State<AddToCartButton> createState() => _AddToCartButtonState();
}

class _AddToCartButtonState extends State<AddToCartButton> {
  bool _saving = false;
  bool _checkCartFirst = false;
  String? _message;

  Future<void> _add() async {
    if (_saving || _checkCartFirst) return;

    setState(() {
      _saving = true;
      _message = null;
    });

    try {
      await widget.service.addProduct(
        clinicId: widget.clinicId,
        productId: widget.productId,
      );

      if (!mounted) return;
      setState(() => _message = 'Added to cart.');
    } catch (error) {
      if (!mounted) return;

      final status = error is ApiException ? error.statusCode : null;
      final uncertain = status == null ||
          status >= 500 ||
          (status >= 200 && status < 300);

      setState(() {
        _checkCartFirst = uncertain;
        _message = uncertain
            ? 'Could not confirm the update. Open your cart to check '
            'before adding this product again.'
            : error.toString();
      });
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        FilledButton.icon(
          onPressed: widget.inStock && !_saving && !_checkCartFirst
              ? _add
              : null,
          icon: const Icon(Icons.add_shopping_cart),
          label: Text(
            _saving
                ? 'Adding…'
                : widget.inStock
                ? 'Add to Cart'
                : 'Out of stock',
          ),
        ),
        if (_message != null) ...[
          const SizedBox(height: 8),
          Text(_message!, textAlign: TextAlign.center),
        ],
      ],
    );
  }
}