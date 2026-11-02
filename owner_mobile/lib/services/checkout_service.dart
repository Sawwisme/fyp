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
}