import 'package:flutter/material.dart';

import '../config/api_config.dart';
import '../services/shop_service.dart';
import '../services/cart_service.dart';
import 'my_carts.dart';
import 'add_to_cart_button.dart';
import '../services/checkout_service.dart';
import 'shop_orders.dart';
import 'package:geolocator/geolocator.dart';
import 'package:latlong2/latlong.dart';
import 'dart:async';
import '../services/profile_service.dart';

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
  static const _green = Color(0xFF2549C7);
  static const _pageSize = 10;
  LatLng? _ownerLocation;
  bool _locating = false;
  String? _locationMessage;

  final _searchController = TextEditingController();

  late Future<List<Map<String, dynamic>>> _future;

  Map<String, dynamic>? _clinic;
  int? _categoryId;
  Future<List<Map<String, dynamic>>>? _categoriesFuture;
  String _query = '';
  String? _clinicState;
  String? _fulfilment;
  String? _deliveryState;
  bool _destinationEdited = false;

  static const _states = [
    'Johor', 'Kedah', 'Kelantan', 'Melaka',
    'Negeri Sembilan', 'Pahang', 'Pulau Pinang',
    'Perak', 'Perlis', 'Sabah', 'Sarawak',
    'Selangor', 'Terengganu',
    'W.P. Kuala Lumpur', 'W.P. Labuan', 'W.P. Putrajaya',
  ];
  int _page = 0;
  bool _openingProduct = false;

  int? _cartQuantity;
  int _cartCountRequest = 0;

  Future<void> _refreshCartCount() async {
    final request = ++_cartCountRequest;

    try {
      final carts =
      await CartService(widget.service.api).getMyCarts();

      if (!mounted || request != _cartCountRequest) return;

      final quantity = carts.fold<int>(
        0,
            (total, cart) =>
        total + (cart['total_quantity'] as num).toInt(),
      );

      setState(() => _cartQuantity = quantity);
    } catch (_) {
      if (!mounted || request != _cartCountRequest) return;

      // Unknown is different from an empty cart.
      setState(() => _cartQuantity = null);
    }
  }

  @override
  void initState() {
    super.initState();
    unawaited(_prefillDeliveryState());
    _future = _loadInitialShop();
    CartService.changes.addListener(_refreshCartCount);
    _refreshCartCount();
  }

  @override
  void dispose() {
    CartService.changes.removeListener(_refreshCartCount);
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _prefillDeliveryState() async {
    try {
      final profile =
      await ProfileService(widget.service.api).getProfile();

      if (!mounted || _destinationEdited) return;

      final state = profile['default_state'];

      if (state is String && _states.contains(state)) {
        setState(() => _deliveryState = state);

        if (_clinic == null && _fulfilment == 'delivery') {
          _load(0);
        }
      }
    } catch (_) {
      // The owner can select a destination manually.
    }
  }

  Future<List<Map<String, dynamic>>> _fetch() async {
    if (_clinic != null) {
      return widget.service.getProducts(
        clinicId: _clinic!['clinic_id'] as int,
        search: _query,
        categoryId: _categoryId,
        offset: _page * _pageSize,
        limit: _pageSize + 1,
      );
    }

    if (_fulfilment == 'delivery' && _deliveryState == null) {
      return [];
    }

    // Without location, keep the existing server search and pagination.
    if (_ownerLocation == null) {
      return widget.service.getClinics(
        search: _query,
        offset: _page * _pageSize,
        limit: _pageSize + 1,
        state: _clinicState,
        fulfilment: _fulfilment,
        deliveryState:
        _fulfilment == 'delivery' ? _deliveryState : null,
      );
    }

    // Load all matching clinics before sorting, so nearby clinics
    // aren't limited to whichever clinics happened to be on page one.
    final clinics = <Map<String, dynamic>>[];

    for (var offset = 0; ; offset += 100) {
      final page = await widget.service.getClinics(
        search: _query,
        offset: offset,
        limit: 100,
        state: _clinicState,
        fulfilment: _fulfilment,
        deliveryState:
        _fulfilment == 'delivery' ? _deliveryState : null,
      );

      clinics.addAll(page);
      if (page.length < 100) break;
    }

    clinics.sort((a, b) {
      final distanceA = _distanceToClinicKm(a) ?? double.infinity;
      final distanceB = _distanceToClinicKm(b) ?? double.infinity;
      return distanceA.compareTo(distanceB);
    });

    final start = _page * _pageSize;
    return clinics.skip(start).take(_pageSize + 1).toList();
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
      _categoryId = null;
      _categoriesFuture = clinic == null
          ? null
          : widget.service.getCategories(
        clinic['clinic_id'] as int,
      );
      _query = '';
      _page = 0;
      _future = _fetch();
    });
  }

  LatLng? _clinicCoordinates(Map<String, dynamic> clinic) {
    final lat = double.tryParse('${clinic['latitude'] ?? ''}');
    final lng = double.tryParse('${clinic['longitude'] ?? ''}');

    if (lat == null || lng == null ||
        !lat.isFinite || !lng.isFinite ||
        lat < -90 || lat > 90 || lng < -180 || lng > 180) {
      return null;
    }

    return LatLng(lat, lng);
  }

  double? _distanceToClinicKm(Map<String, dynamic> clinic) {
    final owner = _ownerLocation;
    final coordinates = _clinicCoordinates(clinic);

    if (owner == null || coordinates == null) return null;

    return const Distance().as(
      LengthUnit.Kilometer,
      owner,
      coordinates,
    );
  }

  Future<List<Map<String, dynamic>>> _loadInitialShop() async {
    final clinics = <Map<String, dynamic>>[];

    // Read all pages before finding the most-visited clinic.
    for (var offset = 0; ; offset += 100) {
      final page = await widget.service.getClinics(
        offset: offset,
        limit: 100,
      );

      clinics.addAll(page);

      if (page.length < 100) break;
    }

    if (!mounted) return [];

    clinics.sort((a, b) {
      final aVisits =
          (a['completed_visit_count'] as num?)?.toInt() ?? 0;
      final bVisits =
          (b['completed_visit_count'] as num?)?.toInt() ?? 0;

      final byVisits = bVisits.compareTo(aVisits);

      if (byVisits != 0) return byVisits;

      return '${a['clinic_name']}'
          .compareTo('${b['clinic_name']}');
    });

    final mostVisited = clinics.isEmpty ? null : clinics.first;

    final visitCount =
        (mostVisited?['completed_visit_count'] as num?)?.toInt() ?? 0;

    if (mostVisited != null && visitCount > 0) {
      _clinic = mostVisited;
      _categoriesFuture = widget.service.getCategories(
        mostVisited['clinic_id'] as int,
      );

      return widget.service.getProducts(
        clinicId: mostVisited['clinic_id'] as int,
        limit: _pageSize + 1,
      );
    }

    // Owners without completed visits choose a clinic themselves.
    return clinics.take(_pageSize + 1).toList();
  }

  Future<void> _chooseShopClinic() async {
    final selected = await showModalBottomSheet<Map<String, dynamic>>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      showDragHandle: true,
      backgroundColor: Colors.white,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(
          top: Radius.circular(24),
        ),
      ),
      builder: (_) => _ShopClinicDialog(
        service: widget.service,
        selectedClinicId: _clinic?['clinic_id'] as int?,
      ),
    );

    if (!mounted || selected == null) return;

    _selectClinic(selected);
  }

  Future<void> _useMyLocation() async {
    if (_locating) return;

    setState(() {
      _locating = true;
      _locationMessage = null;
    });

    try {
      final enabled = await Geolocator.isLocationServiceEnabled();
      if (!mounted) return;

      if (!enabled) {
        setState(() {
          _locationMessage =
          'Location is switched off. Enable it in your phone settings.';
        });
        await Geolocator.openLocationSettings();
        return;
      }

      var permission = await Geolocator.checkPermission();

      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
      }

      if (!mounted) return;

      if (permission == LocationPermission.deniedForever) {
        setState(() {
          _locationMessage =
          'Allow location access for VetDental in app settings.';
        });
        await Geolocator.openAppSettings();
        return;
      }

      if (permission == LocationPermission.denied) {
        setState(() {
          _locationMessage =
          'Location permission was declined. You can still find a clinic by name.';
        });
        return;
      }

      final position = await Geolocator.getCurrentPosition(
        locationSettings: const LocationSettings(
          accuracy: LocationAccuracy.medium,
          timeLimit: Duration(seconds: 30),
        ),
      );

      if (!mounted) return;

      setState(() {
        _ownerLocation = LatLng(
          position.latitude,
          position.longitude,
        );
        _locationMessage = 'Location found. Showing nearby clinic shops.';
        _query = '';
        _searchController.clear();
      });

      _load(0);
    } catch (error) {
      debugPrint('Shop location failed: $error');

      if (mounted) {
        setState(() {
          _locationMessage =
          'Could not obtain your location. Check phone location '
              'settings and try again.';
        });
      }
    } finally {
      if (mounted) {
        setState(() => _locating = false);
      }
    }
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
                    productName:
                    product['product_name'].toString(),
                    price: num.parse(
                      product['price'].toString(),
                    ).toStringAsFixed(2),
                    stockQuantity: stock,
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

  void _selectCategory(int? categoryId) {
    if (_categoryId == categoryId) return;

    setState(() {
      _categoryId = categoryId;
      _page = 0;
      _future = _fetch();
    });
  }

  Widget _categoryChip(String title, int? categoryId) {
    final selected = _categoryId == categoryId;

    return Padding(
      padding: const EdgeInsets.only(right: 8),
      child: ChoiceChip(
        label: Text(title),
        selected: selected,
        onSelected: (_) => _selectCategory(categoryId),
        showCheckmark: false,
        selectedColor: const Color(0xFFE1F0E5),
        backgroundColor: Colors.white,
        labelStyle: TextStyle(
          color: selected ? _green : Colors.black87,
          fontWeight: selected
              ? FontWeight.w600
              : FontWeight.normal,
        ),
        side: BorderSide(
          color: selected
              ? _green
              : const Color(0xFFDDE7DF),
        ),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(10),
        ),
      ),
    );
  }

  Widget _clinicFilters() {
    if (_clinic != null) return const SizedBox.shrink();

    void applyFilter(VoidCallback update) {
      setState(() {
        update();
        _page = 0;
        _future = _fetch();
      });
    }

    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 0, 20, 16),
      child: LayoutBuilder(
        builder: (context, constraints) {
          final width = constraints.maxWidth < 500
              ? constraints.maxWidth
              : (constraints.maxWidth - 12) / 2;

          return Wrap(
            spacing: 12,
            runSpacing: 12,
            children: [
              SizedBox(
                width: width,
                child: DropdownButtonFormField<String>(
                  key: ValueKey('clinic-state-$_clinicState'),
                  initialValue: _clinicState ?? '',
                  isExpanded: true,
                  decoration: const InputDecoration(
                    labelText: 'Clinic state',
                    border: OutlineInputBorder(),
                  ),
                  items: [
                    const DropdownMenuItem(
                      value: '',
                      child: Text('All states'),
                    ),
                    for (final state in _states)
                      DropdownMenuItem(
                        value: state,
                        child: Text(state),
                      ),
                  ],
                  onChanged: (value) {
                    applyFilter(() {
                      _clinicState =
                      value == null || value.isEmpty ? null : value;
                    });
                  },
                ),
              ),
              SizedBox(
                width: width,
                child: DropdownButtonFormField<String>(
                  key: ValueKey('clinic-fulfilment-$_fulfilment'),
                  initialValue: _fulfilment ?? '',
                  isExpanded: true,
                  decoration: const InputDecoration(
                    labelText: 'Fulfilment',
                    border: OutlineInputBorder(),
                  ),
                  items: const [
                    DropdownMenuItem(
                      value: '',
                      child: Text('Pickup or delivery'),
                    ),
                    DropdownMenuItem(
                      value: 'pickup',
                      child: Text('Clinic pickup'),
                    ),
                    DropdownMenuItem(
                      value: 'delivery',
                      child: Text('Delivery available'),
                    ),
                  ],
                  onChanged: (value) {
                    applyFilter(() {
                      _fulfilment =
                      value == null || value.isEmpty ? null : value;
                    });
                  },
                ),
              ),
              if (_fulfilment == 'delivery')
                SizedBox(
                  width: width,
                  child: DropdownButtonFormField<String>(
                    key: ValueKey('shop-destination-$_deliveryState'),
                    initialValue: _deliveryState ?? '',
                    isExpanded: true,
                    decoration: const InputDecoration(
                      labelText: 'Deliver to state',
                      border: OutlineInputBorder(),
                      helperText:
                      'Filters clinics by delivery coverage.',
                    ),
                    items: [
                      const DropdownMenuItem(
                        value: '',
                        child: Text('Select destination'),
                      ),
                      for (final state in _states)
                        DropdownMenuItem(
                          value: state,
                          child: Text(state),
                        ),
                    ],
                    onChanged: (value) {
                      applyFilter(() {
                        _destinationEdited = true;
                        _deliveryState =
                        value == null || value.isEmpty
                            ? null
                            : value;
                      });
                    },
                  ),
                ),
              if (_fulfilment == 'delivery' &&
                  _deliveryState == null)
                const Text(
                  'Select a destination state to find clinics '
                      'that deliver there.',
                ),
            ],
          );
        },
      ),
    );
  }

  Widget _categoryFilter() {
    if (_clinic == null) return const SizedBox.shrink();

    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 0, 20, 12),
      child: FutureBuilder<List<Map<String, dynamic>>>(
        key: ValueKey(_clinic!['clinic_id']),
        future: _categoriesFuture,
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) {
            return const LinearProgressIndicator();
          }

          if (snapshot.hasError) {
            return Row(
              children: [
                const Expanded(
                  child: Text(
                    'Categories unavailable. '
                        'You can still browse all products.',
                    style: TextStyle(color: Colors.black54),
                  ),
                ),
                TextButton(
                  onPressed: () {
                    setState(() {
                      _categoriesFuture =
                          widget.service.getCategories(
                            _clinic!['clinic_id'] as int,
                          );
                    });
                  },
                  child: const Text('Retry'),
                ),
              ],
            );
          }

          final categories = snapshot.data ?? [];

          return SizedBox(
            height: 50,
            child: ListView(
              scrollDirection: Axis.horizontal,
              children: [
                _categoryChip('All categories', null),
                ...categories.map(
                      (category) => _categoryChip(
                    category['category_name'].toString(),
                    category['category_id'] as int,
                  ),
                ),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _clinicCard(Map<String, dynamic> clinic) {
    final visits =
        (clinic['completed_visit_count'] as num?)?.toInt() ?? 0;

    final address = clinic['address']?.toString().trim() ?? '';

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
          child: Icon(
            Icons.local_hospital_outlined,
            color: _green,
          ),
        ),
        title: Text(
          clinic['clinic_name'].toString(),
          style: const TextStyle(
            fontWeight: FontWeight.w600,
          ),
        ),
        subtitle: Padding(
          padding: const EdgeInsets.only(top: 8),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (visits > 0) ...[
                Text(
                  '$visits completed '
                      '${visits == 1 ? 'visit' : 'visits'}',
                  style: const TextStyle(
                    color: _green,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 6),
              ],
              Text(
                address.isNotEmpty
                    ? address
                    : 'Browse this clinic’s dental care products',
              ),
            ],
          ),
        ),
        trailing: const Icon(
          Icons.chevron_right,
          color: _green,
        ),
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
    await Navigator.of(context).push<void>(
      MaterialPageRoute(
        builder: (_) => MyCartsScreen(
          service: CartService(widget.service.api),
        ),
      ),
    );

    if (mounted) {
      _load(_page);
      await _refreshCartCount();
    }
  }

  Widget _shopHeaderAction({
    required String tooltip,
    required IconData icon,
    required VoidCallback onPressed,
    int? badgeCount,
  }) {
    return SizedBox(
      width: 48,
      height: 48,
      child: IconButton(
        tooltip: tooltip,
        onPressed: onPressed,
        icon: Badge(
          isLabelVisible: (badgeCount ?? 0) > 0,
          backgroundColor: const Color(0xFF2549C7),
          textColor: Colors.white,
          label: Text(
            (badgeCount ?? 0) > 99
                ? '99+'
                : '${badgeCount ?? 0}',
          ),
          child: Icon(icon, size: 22),
        ),
        style: IconButton.styleFrom(
          foregroundColor: const Color(0xFF2549C7),
          backgroundColor: Colors.white,
          side: const BorderSide(
            color: Color(0xFFDCE2ED),
          ),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(14),
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(20, 16, 20, 12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                children: [
                  if (_clinic != null) ...[
                    IconButton(
                      tooltip: 'Back to all clinic shops',
                      onPressed: () => _selectClinic(null),
                      icon: const Icon(
                        Icons.arrow_back_rounded,
                        color: Color(0xFF2549C7),
                      ),
                    ),
                    const SizedBox(width: 4),
                  ],
                  const Expanded(
                    child: Text(
                      'Dental care shop',
                      style: TextStyle(
                        fontSize: 24,
                        fontWeight: FontWeight.w800,
                        color: Color(0xFF172333),
                      ),
                    ),
                  ),
                  _shopHeaderAction(
                    tooltip: 'My orders',
                    icon: Icons.receipt_long_outlined,
                    onPressed: _openOrders,
                  ),
                  const SizedBox(width: 8),
                  _shopHeaderAction(
                    tooltip: _cartQuantity == null
                        ? 'My cart'
                        : 'My cart: $_cartQuantity item(s)',
                    icon: Icons.shopping_cart_outlined,
                    onPressed: _openCart,
                    badgeCount: _cartQuantity,
                  ),
                ],
              ),
              const SizedBox(height: 6),
              const Text(
                'Everyday essentials for healthier smiles.',
                style: TextStyle(
                  fontSize: 13,
                  color: Color(0xFF63718A),
                ),
              ),
              const SizedBox(height: 18),

              // Clinic selection stays together in one card.
              Material(
                color: Colors.white,
                borderRadius: BorderRadius.circular(16),
                child: InkWell(
                  onTap: _chooseShopClinic,
                  borderRadius: BorderRadius.circular(16),
                  child: Container(
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(
                        color: const Color(0xFFDCE2ED),
                      ),
                    ),
                    child: Row(
                      children: [
                        Container(
                          width: 42,
                          height: 42,
                          decoration: BoxDecoration(
                            color: const Color(0xFFEEF2FF),
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: const Icon(
                            Icons.storefront_outlined,
                            color: Color(0xFF2549C7),
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                _clinic == null
                                    ? 'Choose your clinic'
                                    : 'Shopping at',
                                style: const TextStyle(
                                  fontSize: 12,
                                  color: Color(0xFF63718A),
                                ),
                              ),
                              const SizedBox(height: 4),
                              Text(
                                _clinic == null
                                    ? 'Find a clinic shop'
                                    : '${_clinic!['clinic_name']}',
                                maxLines: 2,
                                overflow: TextOverflow.ellipsis,
                                style: const TextStyle(
                                  fontSize: 15,
                                  fontWeight: FontWeight.w700,
                                  color: Color(0xFF172333),
                                ),
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(width: 8),
                        const Icon(
                          Icons.chevron_right_rounded,
                          color: Color(0xFF2549C7),
                        ),
                      ],
                    ),
                  ),
                ),
              ),

              if (_clinic == null) ...[
                const SizedBox(height: 8),
                Align(
                  alignment: Alignment.centerLeft,
                  child: TextButton.icon(
                    onPressed: _locating ? null : _useMyLocation,
                    icon: _locating
                        ? const SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                      ),
                    )
                        : const Icon(
                      Icons.near_me_outlined,
                      size: 18,
                    ),
                    label: Text(
                      _locating
                          ? 'Finding nearby clinics…'
                          : 'Find shops near me',
                    ),
                    style: TextButton.styleFrom(
                      foregroundColor: const Color(0xFF2549C7),
                    ),
                  ),
                ),
                if (_locationMessage != null)
                  Padding(
                    padding: const EdgeInsets.only(
                      left: 12,
                      bottom: 4,
                    ),
                    child: Text(
                      _locationMessage!,
                      style: const TextStyle(
                        fontSize: 12,
                        color: Color(0xFF63718A),
                      ),
                    ),
                  ),
              ],

              if (_clinic != null) ...[
                const SizedBox(height: 14),
                TextField(
                  controller: _searchController,
                  textInputAction: TextInputAction.search,
                  decoration: InputDecoration(
                    hintText: 'Search this clinic’s products',
                    prefixIcon: const Icon(
                      Icons.search_rounded,
                      color: Color(0xFF63718A),
                    ),
                    suffixIcon: IconButton(
                      tooltip: 'Search products',
                      icon: const Icon(
                        Icons.arrow_forward_rounded,
                      ),
                      onPressed: () {
                        _query = _searchController.text.trim();
                        _load();
                      },
                    ),
                    filled: true,
                    fillColor: Colors.white,
                    contentPadding: const EdgeInsets.symmetric(
                      horizontal: 16,
                      vertical: 14,
                    ),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(14),
                      borderSide: const BorderSide(
                        color: Color(0xFFDCE2ED),
                      ),
                    ),
                    enabledBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(14),
                      borderSide: const BorderSide(
                        color: Color(0xFFDCE2ED),
                      ),
                    ),
                    focusedBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(14),
                      borderSide: const BorderSide(
                        color: Color(0xFF2549C7),
                        width: 1.5,
                      ),
                    ),
                  ),
                  onSubmitted: (value) {
                    _query = value.trim();
                    _load();
                  },
                ),
              ],
            ],
          ),
        ),

        _clinicFilters(),
        _categoryFilter(),

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
                            ? (_query.trim().isEmpty
                            ? 'No clinic shops are available yet. Clinics need to enable '
                            'pickup or delivery and add products with available stock.'
                            : 'No clinic shops match your search and filters. '
                            'Try another state, fulfilment option or clinic name.')
                            : (_query.trim().isEmpty && _categoryId == null
                            ? 'This clinic has no products available right now.'
                            : 'No products match your filters.'),
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

class _ShopClinicDialog extends StatefulWidget {
  final ShopService service;
  final int? selectedClinicId;

  const _ShopClinicDialog({
    required this.service,
    this.selectedClinicId,
  });

  @override
  State<_ShopClinicDialog> createState() =>
      _ShopClinicDialogState();
}

class _ShopClinicDialogState extends State<_ShopClinicDialog> {
  final _search = TextEditingController();
  Timer? _searchDebounce;

  List<Map<String, dynamic>> _clinics = [];

  bool _loading = true;
  bool _hasMore = false;
  String? _error;

  String _query = '';
  int _offset = 0;
  int _requestVersion = 0;

  static const _limit = 20;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _searchDebounce?.cancel();
    _search.dispose();
    super.dispose();
  }
  
  Future<void> _load({bool loadMore = false}) async {
    final version = ++_requestVersion;
    final offset = loadMore ? _offset : 0;

    setState(() {
      _loading = true;
      _error = null;

      if (!loadMore) {
        _clinics = [];
        _offset = 0;
        _hasMore = false;
      }
    });

    try {
      final results = await widget.service.getClinics(
        search: _query,
        offset: offset,
        limit: _limit + 1,
      );

      if (!mounted || version != _requestVersion) return;

      final page = results.take(_limit).toList();

      setState(() {
        _clinics = loadMore
            ? [..._clinics, ...page]
            : page;

        _offset = offset + page.length;
        _hasMore = results.length > _limit;
      });
    } catch (_) {
      if (!mounted || version != _requestVersion) return;

      setState(() {
        _error = 'Could not load clinics. Please try again.';
      });
    } finally {
      if (mounted && version == _requestVersion) {
        setState(() => _loading = false);
      }
    }
  }

  void _submitSearch() {
    _searchDebounce?.cancel();
    _query = _search.text.trim();
    _load();
  }

  void _onSearchChanged(String value) {
    _searchDebounce?.cancel();

    // Prevent an earlier response from replacing the new search results.
    _requestVersion++;

    setState(() {
      _loading = true;
      _hasMore = false;
    });

    _searchDebounce = Timer(
      const Duration(milliseconds: 350),
          () {
        if (!mounted) return;

        _query = value.trim();
        _load();
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.white,
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 540),
        child: SizedBox(
          height: MediaQuery.sizeOf(context).height * 0.75,
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        'Choose a clinic',
                        style: Theme.of(context)
                            .textTheme
                            .titleLarge,
                      ),
                    ),
                    IconButton(
                      tooltip: 'Close',
                      onPressed: () => Navigator.of(context).pop(),
                      icon: const Icon(Icons.close_rounded),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _search,
                  textInputAction: TextInputAction.search,
                  onChanged: _onSearchChanged,
                  onSubmitted: (_) => _submitSearch(),
                  decoration: InputDecoration(
                    hintText: 'Search clinic name, town or state',
                    prefixIcon: const Icon(Icons.search_rounded),
                    suffixIcon: IconButton(
                      tooltip: 'Search clinics',
                      onPressed: _submitSearch,
                      icon: const Icon(Icons.arrow_forward_rounded),
                    ),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                  ),
                ),
                const SizedBox(height: 12),
                const Text(
                  'Choose the clinic whose products you want to browse.',
                ),
                const SizedBox(height: 12),
                Expanded(
                  child: _loading && _clinics.isEmpty
                      ? const Center(
                    child: CircularProgressIndicator(),
                  )
                      : ListView(
                    children: [
                      if (!_loading &&
                          _error == null &&
                          _clinics.isEmpty)
                        const Padding(
                          padding: EdgeInsets.all(24),
                          child: Text(
                            'No matching clinics found. '
                                'Try another clinic name.',
                            textAlign: TextAlign.center,
                          ),
                        ),
                      for (final clinic in _clinics)
                        _clinicTile(clinic),
                      if (_loading)
                        const Padding(
                          padding: EdgeInsets.all(16),
                          child: Center(
                            child: CircularProgressIndicator(),
                          ),
                        ),
                      if (_error != null) ...[
                        Text(
                          _error!,
                          textAlign: TextAlign.center,
                        ),
                        TextButton(
                          onPressed: () => _load(
                            loadMore: _clinics.isNotEmpty,
                          ),
                          child: const Text('Try again'),
                        ),
                      ] else if (_hasMore && !_loading)
                        TextButton(
                          onPressed: () => _load(loadMore: true),
                          child: const Text('Show more clinics'),
                        ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _clinicTile(Map<String, dynamic> clinic) {
    final selected =
        clinic['clinic_id'] == widget.selectedClinicId;

    final visits =
        (clinic['completed_visit_count'] as num?)?.toInt() ?? 0;

    final address = '${clinic['address'] ?? ''}'.trim();

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      decoration: BoxDecoration(
        color: selected
            ? const Color(0xFFEEF2FF)
            : const Color(0xFFF8F9FC),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: selected
              ? const Color(0xFF2549C7)
              : const Color(0xFFE1E6EF),
        ),
      ),
      child: ListTile(
        contentPadding: const EdgeInsets.all(14),
        leading: Container(
          padding: const EdgeInsets.all(10),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(12),
          ),
          child: const Icon(
            Icons.storefront_rounded,
            color: Color(0xFF2549C7),
          ),
        ),
        title: Text(
          '${clinic['clinic_name']}',
          style: const TextStyle(
            fontWeight: FontWeight.w700,
            color: Color(0xFF172333),
          ),
        ),
        subtitle: Padding(
          padding: const EdgeInsets.only(top: 6),
          child: Text(
            [
              if (address.isNotEmpty) address,
              if (visits > 0)
                '$visits completed ${visits == 1 ? 'visit' : 'visits'}',
            ].join('\n'),
            style: const TextStyle(
              color: Color(0xFF63718A),
              height: 1.5,
            ),
          ),
        ),
        trailing: Icon(
          selected
              ? Icons.check_circle_rounded
              : Icons.chevron_right_rounded,
          color: const Color(0xFF2549C7),
        ),
        onTap: () => Navigator.of(context).pop(clinic),
      ),
    );
  }
}