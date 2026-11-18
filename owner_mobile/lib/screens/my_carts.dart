import 'package:flutter/material.dart';

import '../services/cart_service.dart';
import '../services/checkout_service.dart';
import 'checkout.dart';
import '../config/api_config.dart';

class MyCartsScreen extends StatefulWidget {
  final CartService service;

  const MyCartsScreen({
    super.key,
    required this.service,
  });

  @override
  State<MyCartsScreen> createState() => _MyCartsScreenState();
}

class _MyCartsScreenState extends State<MyCartsScreen> {
  static const _blue = Color(0xFF2549C7);

  List<Map<String, dynamic>> _carts = [];
  final Set<int> _selected = {};

  int? _selectedClinic;
  bool _loading = true;
  bool _busy = false;
  bool _needsRefresh = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  List<Map<String, dynamic>> _items(Map<String, dynamic> cart) {
    return (cart['items'] as List? ?? [])
        .whereType<Map>()
        .map((item) => Map<String, dynamic>.from(item))
        .toList();
  }

  String _money(dynamic value) {
    return num.tryParse('$value')?.toStringAsFixed(2) ?? '—';
  }

  void _notice(String text) {
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(text)));
  }

  Future<void> _load() async {
    if (_busy) return;

    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final carts = await widget.service.getMyCarts();
      if (!mounted) return;

      final validIds = <int>{
        for (final cart in carts)
          for (final item in _items(cart))
            if (item['available'] == true)
              item['product_id'] as int,
      };

      setState(() {
        _carts = carts;
        _selected.retainAll(validIds);
        if (_selected.isEmpty) _selectedClinic = null;
        _needsRefresh = false;
      });
    } catch (error) {
      if (mounted) {
        setState(() => _error = error.toString());
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _toggle(
      Map<String, dynamic> cart,
      List<int> ids,
      bool select,
      ) {
    if (_busy || _loading || _needsRefresh) return;

    final clinicId = cart['clinic_id'] as int;

    if (select &&
        _selectedClinic != null &&
        _selectedClinic != clinicId) {
      _notice(
        'Checkout one clinic at a time. '
            'Deselect your current items first.',
      );
      return;
    }

    if (select && {..._selected, ...ids}.length > 50) {
      _notice('Select up to 50 different products per checkout.');
      return;
    }

    setState(() {
      if (select) {
        _selected.addAll(ids);
        if (_selected.isNotEmpty) _selectedClinic = clinicId;
      } else {
        _selected.removeAll(ids);
        if (_selected.isEmpty) _selectedClinic = null;
      }
    });
  }

  Widget _productPhoto(dynamic imageUrl) {
    final path = imageUrl?.toString() ?? '';

    final valid = RegExp(
      r'^/clinic-products/images/[a-f0-9]{32}\.jpg$',
    ).hasMatch(path);

    const placeholder = Center(
      child: Icon(
        Icons.shopping_bag_outlined,
        color: Color(0xFF8A96AC),
      ),
    );

    return Container(
      width: 52,
      height: 52,
      clipBehavior: Clip.antiAlias,
      decoration: BoxDecoration(
        color: const Color(0xFFF0F3FA),
        borderRadius: BorderRadius.circular(10),
      ),
      child: valid
          ? Image.network(
        Uri.parse(ApiConfig.baseUrl)
            .resolve(path)
            .toString(),
        fit: BoxFit.contain,
        errorBuilder: (_, _, _) => placeholder,
      )
          : placeholder,
    );
  }

  Future<void> _changeQuantity(
      Map<String, dynamic> cart,
      Map<String, dynamic> item,
      int quantity,
      ) async {
    if (_busy || _loading || _needsRefresh) return;

    if (quantity == 0) {
      final remove = await showDialog<bool>(
        context: context,
        builder: (dialogContext) => AlertDialog(
          title: const Text('Remove product?'),
          content: Text('${item['product_name']}'),
          actions: [
            TextButton(
              onPressed: () =>
                  Navigator.of(dialogContext).pop(false),
              child: const Text('Keep'),
            ),
            TextButton(
              onPressed: () =>
                  Navigator.of(dialogContext).pop(true),
              child: const Text('Remove'),
            ),
          ],
        ),
      );

      if (!mounted || remove != true) return;
    }

    if (_busy || _loading || _needsRefresh) return;

    setState(() => _busy = true);

    try {
      final updated = await widget.service.setQuantity(
        clinicId: cart['clinic_id'] as int,
        productId: item['product_id'] as int,
        expectedVersion: cart['version'] as int,
        quantity: quantity,
      );

      if (!mounted) return;

      setState(() {
        final index = _carts.indexWhere(
              (entry) => entry['clinic_id'] == updated['clinic_id'],
        );

        if (index >= 0) {
          if (_items(updated).isEmpty) {
            _carts.removeAt(index);
          } else {
            _carts[index] = updated;
          }
        }

        final availableIds = <int>{
          for (final entry in _carts)
            for (final product in _items(entry))
              if (product['available'] == true)
                product['product_id'] as int,
        };

        _selected.retainAll(availableIds);
        if (_selected.isEmpty) _selectedClinic = null;
      });
    } catch (error) {
      if (!mounted) return;

      setState(() => _needsRefresh = true);
      _notice(
        'Could not confirm the cart update. '
            'Refresh and review quantities before trying again.',
      );
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _checkout() async {
    if (_busy ||
        _loading ||
        _needsRefresh ||
        _selectedClinic == null ||
        _selected.isEmpty) {
      return;
    }

    final ids = _selected.toList()..sort();

    await Navigator.of(context).push<void>(
      MaterialPageRoute(
        builder: (_) => CheckoutScreen(
          service: CheckoutService(widget.service.api),
          clinicId: _selectedClinic!,
          selectedProductIds: ids,
        ),
      ),
    );

    if (mounted) await _load();
  }

  Widget _product(
      Map<String, dynamic> cart,
      Map<String, dynamic> item,
      ) {
    final id = item['product_id'] as int;
    final quantity = item['quantity'] as int;
    final stock = item['stock_quantity'] as int;
    final enabled = !_busy && !_loading && !_needsRefresh;

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Checkbox(
            value: _selected.contains(id),
            onChanged: enabled && item['available'] == true
                ? (value) => _toggle(cart, [id], value == true)
                : null,
          ),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _productPhoto(item['image_url']),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Text(
                        '${item['product_name']}',
                        style: const TextStyle(
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 6),
                Text(
                  'RM ${_money(item['unit_price'])}',
                  style: const TextStyle(
                    color: _blue,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                if (item['available'] != true)
                  const Text(
                    'Unavailable or insufficient stock',
                    style: TextStyle(
                      color: Colors.red,
                      fontSize: 12,
                    ),
                  ),
                if (item['price_changed'] == true)
                  const Text(
                    'Current price shown; review before checkout.',
                    style: TextStyle(fontSize: 12),
                  ),
                const SizedBox(height: 10),
                Wrap(
                  spacing: 6,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    IconButton.outlined(
                      tooltip: quantity == 1
                          ? 'Remove product'
                          : 'Decrease quantity',
                      onPressed: enabled
                          ? () => _changeQuantity(
                        cart, item, quantity - 1,
                      )
                          : null,
                      icon: Icon(
                        quantity == 1
                            ? Icons.delete_outline
                            : Icons.remove,
                        size: 18,
                      ),
                    ),
                    SizedBox(
                      width: 32,
                      child: Text(
                        '$quantity',
                        textAlign: TextAlign.center,
                      ),
                    ),
                    IconButton.outlined(
                      tooltip: 'Increase quantity',
                      onPressed: enabled &&
                          quantity < stock &&
                          quantity < 99
                          ? () => _changeQuantity(
                        cart, item, quantity + 1,
                      )
                          : null,
                      icon: const Icon(Icons.add, size: 18),
                    ),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          Text(
            'RM ${_money(item['line_total'])}',
            style: const TextStyle(fontWeight: FontWeight.w600),
          ),
        ],
      ),
    );
  }

  Widget _clinicGroup(Map<String, dynamic> cart) {
    final items = _items(cart);
    final availableIds = [
      for (final item in items)
        if (item['available'] == true)
          item['product_id'] as int,
    ];

    final allSelected = availableIds.isNotEmpty &&
        availableIds.every(_selected.contains);

    final someSelected = availableIds.any(_selected.contains);

    return Card(
      color: Colors.white,
      elevation: 0,
      margin: const EdgeInsets.only(bottom: 14),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(18),
        side: const BorderSide(color: Color(0xFFDCE2ED)),
      ),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(8, 8, 16, 12),
        child: Column(
          children: [
            Row(
              children: [
                Checkbox(
                  tristate: true,
                  value: allSelected
                      ? true
                      : someSelected
                      ? null
                      : false,
                  onChanged: _busy ||
                      _loading ||
                      _needsRefresh ||
                      availableIds.isEmpty
                      ? null
                      : (_) => _toggle(
                    cart,
                    availableIds,
                    !allSelected,
                  ),
                ),
                const Icon(Icons.storefront_outlined, size: 20),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    '${cart['clinic_name']}',
                    style: const TextStyle(
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
              ],
            ),
            const Divider(height: 1),
            for (final item in items) _product(cart, item),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    num subtotal = 0;
    var selectedQuantity = 0;

    for (final cart in _carts) {
      for (final item in _items(cart)) {
        if (_selected.contains(item['product_id'])) {
          subtotal += num.tryParse('${item['line_total']}') ?? 0;
          selectedQuantity += item['quantity'] as int;
        }
      }
    }

    return Scaffold(
      backgroundColor: const Color(0xFFF3F5FA),
      appBar: AppBar(title: const Text('My cart')),
      body: Column(
        children: [
          if (_busy) const LinearProgressIndicator(),
          if (_needsRefresh || _error != null)
            MaterialBanner(
              content: Text(
                _error ?? 'Refresh to check the latest cart quantities.',
              ),
              actions: [
                TextButton(
                  onPressed: _busy || _loading ? null : _load,
                  child: const Text('Refresh'),
                ),
              ],
            ),
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : RefreshIndicator(
              onRefresh: _load,
              child: ListView(
                physics: const AlwaysScrollableScrollPhysics(),
                padding: const EdgeInsets.all(16),
                children: [
                  const Padding(
                    padding: EdgeInsets.only(bottom: 16),
                    child: Text(
                      'Products are grouped by clinic. '
                          'Checkout one clinic at a time.',
                      style: TextStyle(color: Color(0xFF63718A)),
                    ),
                  ),
                  if (_carts.isEmpty && _error == null)
                    const Padding(
                      padding: EdgeInsets.all(40),
                      child: Column(
                        children: [
                          Icon(
                            Icons.shopping_cart_outlined,
                            size: 52,
                          ),
                          SizedBox(height: 16),
                          Text('Your cart is empty'),
                          SizedBox(height: 8),
                          Text('Go back to Shop to add products.'),
                        ],
                      ),
                    ),
                  for (final cart in _carts) _clinicGroup(cart),
                ],
              ),
            ),
          ),
        ],
      ),
      bottomNavigationBar: SafeArea(
        child: Container(
          color: Colors.white,
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              Expanded(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('$selectedQuantity item(s) selected'),
                    Text(
                      'RM ${subtotal.toStringAsFixed(2)}',
                      style: const TextStyle(
                        color: _blue,
                        fontSize: 21,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    const Text(
                      'Delivery fee calculated at checkout',
                      style: TextStyle(fontSize: 11),
                    ),
                  ],
                ),
              ),
              FilledButton(
                onPressed: _selected.isEmpty ||
                    _busy ||
                    _loading ||
                    _needsRefresh
                    ? null
                    : _checkout,
                child: const Text('Checkout'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}