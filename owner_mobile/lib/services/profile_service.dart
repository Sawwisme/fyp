import 'api_client.dart';

class ProfileService {
  final ApiClient api;

  ProfileService(this.api);

  Map<String, dynamic> _validate(dynamic data) {
    if (data is! Map<String, dynamic> ||
        data['user'] is! Map<String, dynamic>) {
      throw const ApiException('Invalid profile response.');
    }

    return data;
  }

  Future<Map<String, dynamic>> getProfile() async {
    return _validate(await api.get('/owners/me'));
  }

  Future<Map<String, dynamic>> updateProfile(
      Map<String, dynamic> body,
      ) async {
    return _validate(await api.patch('/owners/me', body));
  }
}