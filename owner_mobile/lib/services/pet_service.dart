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

    Future<Map<String, dynamic>> createPet(
    Map<String, dynamic> body,
  ) async {
    final data = await api.post('/pets', body);

    if (data is! Map<String, dynamic>) {
      throw const ApiException('Invalid pet registration response.');
    }

    return data;
  }

    Future<Map<String, dynamic>> getPet(int petId) async {
    final data = await api.get('/pets/$petId');

    if (data is! Map<String, dynamic>) {
      throw const ApiException('Invalid pet detail response.');
    }

    return data;
  }

    Future<Map<String, dynamic>> updatePet(
    int petId,
    Map<String, dynamic> body,
  ) async {
    final data = await api.patch('/pets/$petId', body);

    if (data is! Map<String, dynamic>) {
      throw const ApiException('Invalid pet update response.');
    }

    return data;
  }
}