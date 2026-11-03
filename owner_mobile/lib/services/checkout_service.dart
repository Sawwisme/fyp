import 'api_client.dart';
import 'cart_service.dart';

class CheckoutService {
  final ApiClient api;

  CheckoutService(this.api);

  Map<String, dynamic> _readMap(dynamic data) {
    if (data is! Map<String, dynamic>) {
      throw const ApiException('Invalid checkout response.');
    }
    return data;
  }

  Future<Map<String, dynamic>> getCart(int clinicId) {
    return CartService(api).getCart(clinicId);
  }

  Future<Map<String, dynamic>> getSettings(int clinicId) async {
    return _readMap(
      await api.get('/shop/clinics/$clinicId/settings'),
    );
  }

  Future<Map<String, dynamic>> getQuote({
    required int clinicId,
    required int cartVersion,
    required String shippingMethod,
  }) async {
    return _readMap(
      await api.post(
        '/shop/clinics/$clinicId/checkout-quote',
        {
          'expected_cart_version': cartVersion,
          'shipping_method': shippingMethod,
        },
      ),
    );
  }

  Future<Map<String, dynamic>> createOrder({
    required int clinicId,
    required Map<String, dynamic> payload,
  }) async {
    return _readMap(
      await api.post(
        '/shop/clinics/$clinicId/orders',
        payload,
      ),
    );
  }

  Future<Map<String, dynamic>> getOrder(int orderId) async {
    return _readMap(
      await api.get('/shop/orders/$orderId'),
    );
  }

  Future<Map<String, dynamic>> getOrderByCheckoutKey(
      String checkoutKey,
      ) async {
    return _readMap(
      await api.get(
        '/shop/orders/by-checkout-key/'
            '${Uri.encodeComponent(checkoutKey)}',
      ),
    );
  }

  Future<List<Map<String, dynamic>>> getOrders({
    int offset = 0,
    int limit = 20,
  }) async {
    final data = await api.get(
      '/shop/orders?offset=$offset&limit=$limit',
    );

    if (data is! List) {
      throw const ApiException('Invalid orders response.');
    }

    return data.map((item) {
      if (item is! Map) {
        throw const ApiException('Invalid order record.');
      }

      return Map<String, dynamic>.from(item);
    }).toList();
  }

  Future<Map<String, dynamic>> cancelOrder(int orderId) async {
    return _readMap(
      await api.post(
        '/shop/orders/$orderId/cancel',
        {},
      ),
    );
  }
}