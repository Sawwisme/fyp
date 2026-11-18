import 'api_client.dart';
import 'package:flutter/foundation.dart';

class CartService {
  final ApiClient api;

  static final changes = ValueNotifier<int>(0);

  static void notifyChanged() {
    changes.value++;
  }

  CartService(this.api);

  Map<String, dynamic> _readCart(dynamic data) {
    if (data is! Map<String, dynamic> ||
        data['items'] is! List ||
        data['version'] is! int) {
      throw const ApiException('Invalid cart response.');
    }

    return data;
  }

  Future<List<Map<String, dynamic>>> getMyCarts() async {
    final carts = <Map<String, dynamic>>[];
    for (var offset = 0; ; offset += 100) {
      final data = await api.get('/shop/cart?offset=$offset&limit=100');
      if (data is! List) {
        throw const ApiException('Invalid cart list response.');
      }
      carts.addAll(data.map(_readCart));
      if (data.length < 100) return carts;
    }
  }

  Future<Map<String, dynamic>> getCart(int clinicId) async {
    return _readCart(
      await api.get('/shop/cart/$clinicId'),
    );
  }

  Future<Map<String, dynamic>> setQuantity({
    required int clinicId,
    required int productId,
    required int expectedVersion,
    required int quantity,
  }) async {
    final cart = _readCart(
      await api.put(
        '/shop/cart/$clinicId/items/$productId',
        {
          'expected_version': expectedVersion,
          'quantity': quantity,
        },
      ),
    );

    notifyChanged();
    return cart;
  }

  Future<Map<String, dynamic>> addProduct({
    required int clinicId,
    required int productId,
    int quantityToAdd = 1,
  }) async {
    final cart = await getCart(clinicId);
    final items = cart['items'] as List;

    if (quantityToAdd < 1 || quantityToAdd > 99) {
      throw const ApiException('Choose a quantity from 1 to 99.');
    }

    var quantity = quantityToAdd;

    for (final entry in items) {
      final item = Map<String, dynamic>.from(entry as Map);

      if (item['product_id'] == productId) {
        quantity =
            (item['quantity'] as int) + quantityToAdd;
        break;
      }
    }

    if (quantity > 99) {
      throw const ApiException(
        'You can add up to 99 units of one product.',
      );
    }

    return setQuantity(
      clinicId: clinicId,
      productId: productId,
      expectedVersion: cart['version'] as int,
      quantity: quantity,
    );
  }
}