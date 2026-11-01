import 'api_client.dart';

class ShopService {
  final ApiClient api;

  ShopService(this.api);

  List<Map<String, dynamic>> _readList(dynamic data) {
    if (data is! List) {
      throw const ApiException('Invalid shop response.');
    }

    return data.map((item) {
      if (item is! Map<String, dynamic>) {
        throw const ApiException('Invalid shop record.');
      }
      return item;
    }).toList();
  }

  Future<List<Map<String, dynamic>>> getClinics({
    String search = '',
    int offset = 0,
    int limit = 11,
  }) async {
    final query = Uri(queryParameters: {
      'q': search,
      'offset': '$offset',
      'limit': '$limit',
    }).query;

    return _readList(await api.get('/shop/clinics?$query'));
  }

  Future<List<Map<String, dynamic>>> getProducts({
    required int clinicId,
    String search = '',
    int offset = 0,
    int limit = 11,
  }) async {
    final query = Uri(queryParameters: {
      'q': search,
      'offset': '$offset',
      'limit': '$limit',
    }).query;

    return _readList(
      await api.get('/shop/clinics/$clinicId/products?$query'),
    );
  }

  Future<Map<String, dynamic>> getProduct(int productId) async {
    final data = await api.get('/shop/products/$productId');

    if (data is! Map<String, dynamic>) {
      throw const ApiException('Invalid product response.');
    }

    return data;
  }
}