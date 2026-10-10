import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class TokenStorage {
  static const _tokenKey = 'access_token';

  final FlutterSecureStorage _storage;

  TokenStorage({
    FlutterSecureStorage storage = const FlutterSecureStorage(),
  }) : _storage = storage;

  Future<String?> readToken() {
    return _storage.read(key: _tokenKey);
  }

  Future<void> saveToken(String token) {
    return _storage.write(key: _tokenKey, value: token);
  }

  Future<void> clearToken() {
    return _storage.delete(key: _tokenKey);
  }
}