import 'api_client.dart';

class CartService {
  final ApiClient api;

  CartService(this.api);

  Map<String, dynamic> _readCart(dynamic data) {
    if (data is! Map<String, dynamic> ||
        data['items'] is! List ||
        data['version'] is! int) {
      throw const ApiException('Invalid cart response.');
    }

    return data;
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
    return _readCart(
      await api.put(
        '/shop/cart/$clinicId/items/$productId',
        {
          'expected_version': expectedVersion,
          'quantity': quantity,
        },
      ),
    );
  }

  Future<Map<String, dynamic>> addProduct({
    required int clinicId,
    required int productId,
  }) async {
    final cart = await getCart(clinicId);
    final items = cart['items'] as List;

    var quantity = 1;

    for (final entry in items) {
      final item = Map<String, dynamic>.from(entry as Map);

      if (item['product_id'] == productId) {
        quantity = (item['quantity'] as int) + 1;
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