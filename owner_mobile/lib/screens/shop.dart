import 'package:flutter/material.dart';

import '../config/api_config.dart';
import '../services/shop_service.dart';
import '../services/cart_service.dart';
import 'cart.dart';
import 'add_to_cart_button.dart';
import '../services/checkout_service.dart';
import 'shop_orders.dart';

class ShopScreen extends StatefulWidget {
  final ShopService service;

  const ShopScreen({
    super.key,
    required this.service,
  });

  @override
  State<ShopScreen> createState() => _ShopScreenState();
}

class _ShopScreenState extends State<ShopScreen> {
  static const _green = Color(0xFF176B32);
  static const _pageSize = 10;

  final _searchController = TextEditingController();

  late Future<List<Map<String, dynamic>>> _future;

  Map<String, dynamic>? _clinic;
  String _query = '';
  int _page = 0;
  bool _openingProduct = false;

  @override
  void initState() {
    super.initState();
    _future = _fetch();
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  Future<List<Map<String, dynamic>>> _fetch() {
    if (_clinic == null) {
      return widget.service.getClinics(
        search: _query,
        offset: _page * _pageSize,
        limit: _pageSize + 1,
      );
    }

    return widget.service.getProducts(
      clinicId: _clinic!['clinic_id'] as int,
      search: _query,
      offset: _page * _pageSize,
      limit: _pageSize + 1,
    );
  }

  void _load([int page = 0]) {
    setState(() {
      _page = page;
      _future = _fetch();
    });
  }

  void _selectClinic(Map<String, dynamic>? clinic) {
    _searchController.clear();

    setState(() {
      _clinic = clinic;
      _query = '';
      _page = 0;
      _future = _fetch();
    });
  }

  String _price(dynamic value) {
    final amount = num.tryParse(value?.toString() ?? '');
    return amount == null ? '—' : 'RM ${amount.toStringAsFixed(2)}';
  }

  Widget _photo(dynamic imageUrl, {double size = 76}) {
    final path = imageUrl?.toString() ?? '';

    final valid = RegExp(
      r'^/clinic-products/images/[a-f0-9]{32}\.jpg$',
    ).hasMatch(path);

    final placeholder = Center(
      child: Icon(
        Icons.image_outlined,
        size: 30,
        color: Colors.grey.shade400,
      ),
    );

    return Container(
      width: size,
      height: size,
      clipBehavior: Clip.antiAlias,
      decoration: BoxDecoration(
        color: const Color(0xFFF1F5F2),
        borderRadius: BorderRadius.circular(12),
      ),
      child: valid
          ? Image.network(
        Uri.parse(ApiConfig.baseUrl).resolve(path).toString(),
        fit: BoxFit.contain,
        errorBuilder: (_, _, _) => placeholder,
      )
          : placeholder,
    );
  }

  Future<void> _openProduct(Map<String, dynamic> item) async {
    if (_openingProduct) return;
    _openingProduct = true;

    try {
      final product = await widget.service.getProduct(
        item['product_id'] as int,
      );

      if (!mounted) return;

      final stock = product['stock_quantity'] as int;

      await showModalBottomSheet<void>(
        context: context,
        isScrollControlled: true,
        showDragHandle: true,
        backgroundColor: Colors.white,
        builder: (sheetContext) {
          return SafeArea(
            child: SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(24, 0, 24, 28),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Center(
                    child: _photo(product['image_url'], size: 220),
                  ),
                  const SizedBox(height: 20),
                  Text(
                    product['product_name'].toString(),
                    style: const TextStyle(
                      fontSize: 22,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    _price(product['price']),
                    style: const TextStyle(
                      color: _green,
                      fontSize: 21,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    stock > 0 ? '$stock available' : 'Out of stock',
                    style: TextStyle(
                      color: stock > 0 ? _green : Colors.red.shade700,
                    ),
                  ),
                  const SizedBox(height: 20),
                  const Text(
                    'About this product',
                    style: TextStyle(fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    product['description']?.toString().trim().isNotEmpty ==
                        true
                        ? product['description'].toString()
                        : 'No description provided.',
                    style: const TextStyle(height: 1.5),
                  ),
                  const SizedBox(height: 24),
                  AddToCartButton(
                    service: CartService(widget.service.api),
                    clinicId: product['clinic_id'] as int,
                    productId: product['product_id'] as int,
                    inStock: stock > 0,
                  ),
                ],
              ),
            ),
          );
        },
      );
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(error.toString())),
        );
      }
    } finally {
      _openingProduct = false;
    }
  }

  Widget _clinicCard(Map<String, dynamic> clinic) {
    return Card(
      color: Colors.white,
      elevation: 0,
      margin: const EdgeInsets.only(bottom: 12),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(14),
        side: const BorderSide(color: Color(0xFFDDE7DF)),
      ),
      child: ListTile(
        contentPadding: const EdgeInsets.all(16),
        leading: const CircleAvatar(
          backgroundColor: Color(0xFFE6F2E9),
          child: Icon(Icons.local_hospital_outlined, color: _green),
        ),
        title: Text(
          clinic['clinic_name'].toString(),
          style: const TextStyle(fontWeight: FontWeight.w600),
        ),
        subtitle: Padding(
          padding: const EdgeInsets.only(top: 6),
          child: Text(
            clinic['address']?.toString().isNotEmpty == true
                ? clinic['address'].toString()
                : 'Browse this clinic’s dental care products',
          ),
        ),
        trailing: const Icon(Icons.chevron_right, color: _green),
        onTap: () => _selectClinic(clinic),
      ),
    );
  }

  Widget _productCard(Map<String, dynamic> product) {
    final stock = product['stock_quantity'] as int;

    return Card(
      color: Colors.white,
      elevation: 0,
      margin: const EdgeInsets.only(bottom: 12),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(14),
        side: const BorderSide(color: Color(0xFFDDE7DF)),
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(14),
        onTap: () => _openProduct(product),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Row(
            children: [
              _photo(product['image_url']),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      product['product_name'].toString(),
                      style: const TextStyle(
                        fontWeight: FontWeight.w600,
                        fontSize: 16,
                      ),
                    ),
                    const SizedBox(height: 5),
                    Text(
                      product['category']['category_name'].toString(),
                      style: TextStyle(
                        fontSize: 12,
                        color: Colors.grey.shade600,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      _price(product['price']),
                      style: const TextStyle(
                        color: _green,
                        fontWeight: FontWeight.bold,
                        fontSize: 16,
                      ),
                    ),
                    if (stock == 0) ...[
                      const SizedBox(height: 5),
                      Text(
                        'Out of stock',
                        style: TextStyle(
                          color: Colors.red.shade700,
                          fontSize: 12,
                        ),
                      ),
                    ],
                  ],
                ),
              ),
              const Icon(Icons.chevron_right, color: _green),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _openOrders() async {
    await Navigator.of(context).push<void>(
      MaterialPageRoute(
        builder: (_) => ShopOrdersScreen(
          service: CheckoutService(widget.service.api),
        ),
      ),
    );

    if (mounted) _load(_page);
  }

  Future<void> _openCart() async {
    final clinic = _clinic;
    if (clinic == null) return;

    await Navigator.of(context).push<void>(
      MaterialPageRoute(
        builder: (_) => CartScreen(
          service: CartService(widget.service.api),
          clinicId: clinic['clinic_id'] as int,
        ),
      ),
    );

    if (mounted) _load(_page);
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(20, 16, 20, 12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      _clinic == null
                          ? 'Dental care shop'
                          : _clinic!['clinic_name'].toString(),
                      style: const TextStyle(
                        fontSize: 22,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                  if (_clinic != null)
                    IconButton(
                      tooltip: 'View cart',
                      onPressed: _openCart,
                      icon: const Icon(Icons.shopping_cart_outlined),
                    ),

                  if (_clinic != null)
                    TextButton(
                      onPressed: () => _selectClinic(null),
                      child: const Text('Change clinic'),
                    ),
                ],
              ),
              const SizedBox(height: 8),
              Text(
                _clinic == null
                    ? 'Choose a clinic to browse its products.'
                    : 'Products sold by your selected clinic.',
                style: TextStyle(color: Colors.grey.shade600),
              ),
              const SizedBox(height: 12),
              OutlinedButton.icon(
                onPressed: _openOrders,
                icon: const Icon(Icons.receipt_long_outlined),
                label: const Text('My Orders'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: _green,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(10),
                  ),
                ),
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _searchController,
                textInputAction: TextInputAction.search,
                decoration: InputDecoration(
                  hintText: _clinic == null
                      ? 'Search clinics'
                      : 'Search products',
                  prefixIcon: const Icon(Icons.search),
                  suffixIcon: IconButton(
                    tooltip: 'Search',
                    icon: const Icon(Icons.arrow_forward),
                    onPressed: () {
                      _query = _searchController.text.trim();
                      _load();
                    },
                  ),
                  filled: true,
                  fillColor: Colors.white,
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: const BorderSide(
                      color: Color(0xFFDDE7DF),
                    ),
                  ),
                ),
                onSubmitted: (value) {
                  _query = value.trim();
                  _load();
                },
              ),
            ],
          ),
        ),
        Expanded(
          child: FutureBuilder<List<Map<String, dynamic>>>(
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
                          onPressed: () => _load(_page),
                          child: const Text('Try again'),
                        ),
                      ],
                    ),
                  ),
                );
              }

              final items = snapshot.data ?? [];
              final hasMore = items.length > _pageSize;

              return ListView(
                padding: const EdgeInsets.fromLTRB(20, 4, 20, 24),
                children: [
                  if (items.isEmpty)
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 40),
                      child: Text(
                        _clinic == null
                            ? 'No clinic shops match your search.'
                            : 'No products match your search.',
                        textAlign: TextAlign.center,
                      ),
                    ),
                  ...items.take(_pageSize).map(
                        (item) => _clinic == null
                        ? _clinicCard(item)
                        : _productCard(item),
                  ),
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
              );
            },
          ),
        ),
      ],
    );
  }
}