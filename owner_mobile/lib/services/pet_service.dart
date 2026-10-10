import 'api_client.dart';

class PetService {
  final ApiClient api;

  PetService(this.api);

  Future<List<Map<String, dynamic>>> getPets({
    int offset = 0,
    int limit = 20,
  }) async {
    final data = await api.get('/pets?offset=$offset&limit=$limit');

    if (data is! List) {
      throw const ApiException('Invalid pet list response.');
    }

    return data.map((item) {
      if (item is! Map<String, dynamic>) {
        throw const ApiException('Invalid pet response.');
      }
      return item;
    }).toList();
  }
}