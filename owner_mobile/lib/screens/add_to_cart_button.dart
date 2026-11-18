import 'package:flutter/material.dart';

import '../services/api_client.dart';
import '../services/cart_service.dart';
import 'my_carts.dart';

class AddToCartButton extends StatefulWidget {
  final CartService service;
  final int clinicId;
  final int productId;
  final bool inStock;
  final String productName;
  final String price;
  final int stockQuantity;

  const AddToCartButton({
    super.key,
    required this.service,
    required this.clinicId,
    required this.productId,
    required this.inStock,
    required this.productName,
    required this.price,
    required this.stockQuantity,
  });

  @override
  State<AddToCartButton> createState() => _AddToCartButtonState();
}

class _AddToCartButtonState extends State<AddToCartButton> {
  bool _saving = false;
  bool _checkCartFirst = false;
  String? _message;

  int _quantity = 1;

  bool _choosing = false;

  Future<void> _chooseQuantity() async {
    if (_saving || _choosing || _checkCartFirst) return;

    setState(() {
      _choosing = true;
      _message = null;
    });

    int? selected;

    try {
      final cart = await widget.service.getCart(widget.clinicId);
      if (!mounted) return;

      var existingQuantity = 0;

      for (final raw in cart['items'] as List) {
        final item = Map<String, dynamic>.from(raw as Map);

        if (item['product_id'] == widget.productId) {
          existingQuantity = item['quantity'] as int;
          break;
        }
      }

      final stockRemaining =
          widget.stockQuantity - existingQuantity;
      final limitRemaining = 99 - existingQuantity;
      final maximum = stockRemaining < limitRemaining
          ? stockRemaining
          : limitRemaining;

      if (maximum <= 0) {
        setState(() {
          _message =
          'Your cart already contains the maximum available quantity.';
        });
        return;
      }

      var quantity = 1;

      selected = await showModalBottomSheet<int>(
        context: context,
        isScrollControlled: true,
        showDragHandle: true,
        backgroundColor: Colors.white,
        builder: (sheetContext) {
          return StatefulBuilder(
            builder: (context, updateSheet) {
              return SafeArea(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(24, 4, 24, 24),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          const Icon(
                            Icons.shopping_bag_outlined,
                            size: 42,
                            color: Color(0xFF2549C7),
                          ),
                          const SizedBox(width: 14),
                          Expanded(
                            child: Column(
                              crossAxisAlignment:
                              CrossAxisAlignment.start,
                              children: [
                                Text(
                                  widget.productName,
                                  style: const TextStyle(
                                    fontSize: 17,
                                    fontWeight: FontWeight.w700,
                                  ),
                                ),
                                const SizedBox(height: 6),
                                Text(
                                  'RM ${widget.price}',
                                  style: const TextStyle(
                                    fontSize: 20,
                                    fontWeight: FontWeight.w800,
                                    color: Color(0xFF2549C7),
                                  ),
                                ),
                              ],
                            ),
                          ),
                          IconButton(
                            tooltip: 'Close',
                            onPressed: () =>
                                Navigator.of(sheetContext).pop(),
                            icon: const Icon(Icons.close),
                          ),
                        ],
                      ),
                      const Divider(height: 32),
                      Text(
                        '$existingQuantity already in your cart',
                        style: const TextStyle(
                          color: Color(0xFF63718A),
                        ),
                      ),
                      const SizedBox(height: 12),
                      Row(
                        children: [
                          const Expanded(
                            child: Text(
                              'Quantity to add',
                              style: TextStyle(
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ),
                          IconButton.outlined(
                            onPressed: quantity > 1
                                ? () => updateSheet(() => quantity--)
                                : null,
                            icon: const Icon(Icons.remove),
                          ),
                          SizedBox(
                            width: 48,
                            child: Text(
                              '$quantity',
                              textAlign: TextAlign.center,
                              style: const TextStyle(
                                fontWeight: FontWeight.w700,
                                fontSize: 17,
                              ),
                            ),
                          ),
                          IconButton.outlined(
                            onPressed: quantity < maximum
                                ? () => updateSheet(() => quantity++)
                                : null,
                            icon: const Icon(Icons.add),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Text(
                        'You can add up to $maximum more.',
                        style: const TextStyle(
                          fontSize: 12,
                          color: Color(0xFF63718A),
                        ),
                      ),
                      const SizedBox(height: 24),
                      SizedBox(
                        width: double.infinity,
                        child: FilledButton(
                          onPressed: () =>
                              Navigator.of(sheetContext).pop(quantity),
                          child: Text('Add $quantity to cart'),
                        ),
                      ),
                    ],
                  ),
                ),
              );
            },
          );
        },
      );
    } catch (error) {
      if (mounted) {
        setState(() => _message = error.toString());
      }
    } finally {
      if (mounted) {
        setState(() => _choosing = false);
      }
    }

    if (!mounted || selected == null) return;

    setState(() => _quantity = selected!);
    await _add();
  }

  Future<void> _viewCart() async {
    if (_saving) return;

    await Navigator.of(context).push<void>(
      MaterialPageRoute(
        builder: (_) => MyCartsScreen(
          service: widget.service,
        ),
      ),
    );
  }

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
        quantityToAdd: _quantity,
      );

      if (!mounted) return;
      setState(() {
        _message = 'Added $_quantity item(s) to your cart.';
      });
      ScaffoldMessenger.of(context)
        ..hideCurrentSnackBar()
        ..showSnackBar(
          SnackBar(
            content: Text('Added $_quantity item(s) to cart'),
            behavior: SnackBarBehavior.floating,
            action: SnackBarAction(
              label: 'View cart',
              onPressed: () {
                _viewCart();
              },
            ),
          ),
        );
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
        const SizedBox(height: 12),
        FilledButton.icon(
          onPressed: widget.inStock &&
              !_saving &&
              !_choosing &&
              !_checkCartFirst
              ? _chooseQuantity
              : null,
          icon: const Icon(Icons.add_shopping_cart),
          label: Text(
            _saving
                ? 'Adding…'
                : _choosing
                ? 'Loading…'
                : widget.inStock
                ? 'Add to cart'
                : 'Out of stock',
          ),
        ),
        if (_message != null) ...[
          const SizedBox(height: 8),
          Text(_message!, textAlign: TextAlign.center),
        ],
        if (_message != null) ...[
          const SizedBox(height: 12),
          Wrap(
            spacing: 10,
            runSpacing: 8,
            children: [
              OutlinedButton.icon(
                onPressed: _saving ? null : _viewCart,
                icon: const Icon(Icons.shopping_cart_outlined),
                label: const Text('View cart'),
              ),
              TextButton(
                onPressed: _saving
                    ? null
                    : () => Navigator.of(context).pop(),
                child: const Text('Continue shopping'),
              ),
            ],
          ),
        ],
      ],
    );
  }
}