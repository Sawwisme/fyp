import 'package:flutter/material.dart';
import '../services/cart_service.dart';
import 'cart.dart';

class MyCartsScreen extends StatefulWidget {
  final CartService service;
  const MyCartsScreen({super.key, required this.service});
  @override
  State<MyCartsScreen> createState() => _MyCartsScreenState();
}

class _MyCartsScreenState extends State<MyCartsScreen> {
  late Future<List<Map<String, dynamic>>> _future;
  @override
  void initState() {
    super.initState();
    _future = widget.service.getMyCarts();
  }

  void _reload() {
    setState(() => _future = widget.service.getMyCarts());
  }

  Future<void> _open(Map<String, dynamic> cart) async {
    await Navigator.of(context).push<void>(MaterialPageRoute(
      builder: (_) => CartScreen(
        service: widget.service,
        clinicId: cart['clinic_id'] as int,
      ),
    ));
    if (mounted) _reload();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('My carts')),
      body: FutureBuilder<List<Map<String, dynamic>>>(
        future: _future,
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            return Center(child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Text('Could not load your carts.'),
                TextButton(onPressed: _reload, child: const Text('Try again')),
              ],
            ));
          }
          final carts = snapshot.data ?? [];
          if (carts.isEmpty) {
            return const Center(child: Padding(
              padding: EdgeInsets.all(24),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.shopping_cart_outlined, size: 48),
                  SizedBox(height: 16),
                  Text('Your carts are empty', style: TextStyle(
                    fontSize: 20, fontWeight: FontWeight.w700)),
                  SizedBox(height: 8),
                  Text('Browse a clinic shop and add products to get started.',
                    textAlign: TextAlign.center),
                ],
              ),
            ));
          }
          return ListView.separated(
            padding: const EdgeInsets.all(20),
            itemCount: carts.length,
            separatorBuilder: (_, _) => const SizedBox(height: 12),
            itemBuilder: (context, index) {
              final cart = carts[index];
              final subtotal = num.tryParse('${cart['subtotal']}');
              return Card(child: ListTile(
                contentPadding: const EdgeInsets.all(16),
                leading: const Icon(Icons.storefront_outlined),
                title: Text('${cart['clinic_name']}'),
                subtitle: Text('${cart['total_quantity']} items · '
                  'RM ${subtotal?.toStringAsFixed(2) ?? '—'}'
                  '${cart['can_checkout'] == true ? '' : '\nSome items need attention'}'),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => _open(cart),
              ));
            },
          );
        },
      ),
    );
  }
}
