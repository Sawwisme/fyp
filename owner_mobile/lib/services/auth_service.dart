import 'api_client.dart';

class AuthService {
  final ApiClient api;

  AuthService(this.api);

  Future<Map<String, dynamic>> login({
    required String email,
    required String password,
  }) async {
    final data = await api.post(
      '/auth/login',
      {
        'email': email.trim(),
        'password': password,
      },
      authenticated: false,
    );

    if (data is! Map<String, dynamic>) {
      throw const ApiException('Invalid login response.');
    }

    final token = data['access_token'];
    final user = data['user'];

    if (token is! String ||
        token.isEmpty ||
        user is! Map<String, dynamic>) {
      throw const ApiException('Invalid login response.');
    }

    if (user['role'] != 'pet_owner') {
      throw const ApiException(
        'This application is for pet owners.',
      );
    }

    await api.tokenStorage.saveToken(token);
    return user;
  }

  Future<void> register({
    required String fullName,
    required String email,
    required String password,
    String? phoneNumber,
    String? defaultAddress,
  }) async {
    await api.post(
      '/auth/register',
      {
        'full_name': fullName.trim(),
        'email': email.trim(),
        'password': password,
        'phone_number': phoneNumber,
        'default_address': defaultAddress,
      },
      authenticated: false,
    );
  }

  Future<Map<String, dynamic>> getCurrentUser() async {
    final data = await api.get('/auth/me');

    if (data is! Map<String, dynamic>) {
      throw const ApiException('Invalid account response.');
    }

    return data;
  }

  Future<void> logout() {
    return api.tokenStorage.clearToken();
  }

  Future<void> changePassword({
    required String currentPassword,
    required String newPassword,
  }) async {
    await api.post('/auth/change-password', {
      'current_password': currentPassword,
      'new_password': newPassword,
    });
  }

  Future<String> requestPasswordReset(String email) async {
    final data = await api.post(
      '/auth/forgot-password',
      {'email': email.trim()},
      authenticated: false,
    );

    if (data is! Map<String, dynamic> || data['message'] is! String) {
      throw const ApiException('Invalid password-reset response.');
    }

    return data['message'] as String;
  }
}