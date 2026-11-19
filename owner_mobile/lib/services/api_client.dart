import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:http/http.dart' as http;

import '../config/api_config.dart';
import 'token_storage.dart';

class ApiException implements Exception {
  final String message;
  final int? statusCode;

  const ApiException(this.message, {this.statusCode});

  @override
  String toString() => message;
}

class ApiClient {
  final TokenStorage tokenStorage;
  final http.Client _client;

  ApiClient({
    required this.tokenStorage,
    http.Client? client,
  }) : _client = client ?? http.Client();

  Future<dynamic> get(
    String path, {
    bool authenticated = true,
  }) {
    return _request('GET', path, authenticated: authenticated);
  }

  Future<dynamic> post(
    String path,
    Map<String, dynamic> body, {
    bool authenticated = true,
  }) {
    return _request(
      'POST',
      path,
      body: body,
      authenticated: authenticated,
    );
  }

  Future<dynamic> patch(
    String path,
    Map<String, dynamic> body, {
    bool authenticated = true,
  }) {
    return _request(
      'PATCH',
      path,
      body: body,
      authenticated: authenticated,
    );
  }

  Future<dynamic> put(
      String path,
      Map<String, dynamic> body, {
        bool authenticated = true,
      }) {
    return _request(
      'PUT',
      path,
      body: body,
      authenticated: authenticated,
    );
  }

  Future<dynamic> _request(
    String method,
    String path, {
    Map<String, dynamic>? body,
    required bool authenticated,
  }) async {
    final headers = <String, String>{
      'Accept': 'application/json',
      'Content-Type': 'application/json',
    };

    if (authenticated) {
      final token = await tokenStorage.readToken();

      if (token == null || token.isEmpty) {
        throw const ApiException(
          'Please log in to continue.',
          statusCode: 401,
        );
      }

      headers['Authorization'] = 'Bearer $token';
    }

    final uri = Uri.parse('${ApiConfig.baseUrl}$path');
    late http.Response response;

    try {
      switch (method) {
        case 'GET':
          response = await _client
              .get(uri, headers: headers)
              .timeout(ApiConfig.timeout);
        case 'POST':
          response = await _client
              .post(uri, headers: headers, body: jsonEncode(body))
              .timeout(ApiConfig.timeout);
        case 'PATCH':
          response = await _client
              .patch(uri, headers: headers, body: jsonEncode(body))
              .timeout(ApiConfig.timeout);
        case 'PUT':
          response = await _client
              .put(uri, headers: headers, body: jsonEncode(body))
              .timeout(ApiConfig.timeout);
        default:
          throw ArgumentError('Unsupported request method');
      }
    } on TimeoutException {
      throw const ApiException(
        'The request timed out. Please try again.',
      );
    } on http.ClientException {
      throw const ApiException(
        'Cannot connect to the server. Check your connection.',
      );
    }

    dynamic data;

    try {
      data = response.body.isEmpty
          ? null
          : jsonDecode(utf8.decode(response.bodyBytes));
    } on FormatException {
      throw ApiException(
        'The server returned an unexpected response.',
        statusCode: response.statusCode,
      );
    }

    if (response.statusCode >= 200 && response.statusCode < 300) {
      return data;
    }

    if (authenticated && response.statusCode == 401) {
      await tokenStorage.clearToken();
    }

    var message = 'Request failed. Please try again.';

    if (data is Map<String, dynamic>) {
      final detail = data['detail'];

      if (detail is String) {
        message = detail;
      } else if (detail is List && detail.isNotEmpty) {
        final first = detail.first;

        if (first is Map<String, dynamic> && first['msg'] is String) {
          message = first['msg'] as String;
        }
      }
    }

    throw ApiException(message, statusCode: response.statusCode);
  }

  Future<Map<String, String>> _mediaHeaders() async {
    final token = await tokenStorage.readToken();

    if (token == null || token.isEmpty) {
      throw const ApiException(
        'Please log in to continue.',
        statusCode: 401,
      );
    }

    return {'Authorization': 'Bearer $token'};
  }

  Future<dynamic> _decodeMediaResponse(http.Response response) async {
    if (response.statusCode == 401) {
      await tokenStorage.clearToken();
    }

    dynamic data;

    try {
      data = response.bodyBytes.isEmpty
          ? null
          : jsonDecode(utf8.decode(response.bodyBytes));
    } on FormatException {
      throw ApiException(
        'The server returned an unexpected response.',
        statusCode: response.statusCode,
      );
    }

    if (response.statusCode >= 200 && response.statusCode < 300) {
      return data;
    }

    var message = 'Request failed. Please try again.';

    if (data is Map<String, dynamic>) {
      final detail = data['detail'];

      if (detail is String) {
        message = detail;
      } else if (detail is List && detail.isNotEmpty) {
        final first = detail.first;

        if (first is Map<String, dynamic> && first['msg'] is String) {
          message = first['msg'] as String;
        }
      }
    }

    throw ApiException(message, statusCode: response.statusCode);
  }

  Future<dynamic> postMultipart(
      String path, {
        required Map<String, String> fields,
        required List<http.MultipartFile> files,
        Duration timeout = const Duration(seconds: 60),
      }) async {
    final request = http.MultipartRequest(
      'POST',
      Uri.parse('${ApiConfig.baseUrl}$path'),
    );

    request.headers.addAll(await _mediaHeaders());
    request.headers['Accept'] = 'application/json';
    request.fields.addAll(fields);
    request.files.addAll(files);

    late http.Response response;

    try {
      response = await _client
          .send(request)
          .then((stream) => http.Response.fromStream(stream))
          .timeout(timeout);
    } on TimeoutException {
      throw const ApiException(
        'Upload timed out. Check submission history before retrying.',
      );
    } on http.ClientException {
      throw const ApiException(
        'Connection interrupted. Check submission history before retrying.',
      );
    }

    return _decodeMediaResponse(response);
  }

  Future<Uint8List> getBytes(String path) async {
    final headers = await _mediaHeaders();
    late http.Response response;

    try {
      response = await _client
          .get(
        Uri.parse('${ApiConfig.baseUrl}$path'),
        headers: headers,
      )
          .timeout(ApiConfig.timeout);
    } on TimeoutException {
      throw const ApiException('Loading the photo timed out.');
    } on http.ClientException {
      throw const ApiException('Unable to load the photo.');
    }

    if (response.statusCode >= 200 && response.statusCode < 300) {
      return response.bodyBytes;
    }

    await _decodeMediaResponse(response);
    throw const ApiException('Unable to load the photo.');
  }

  void close() {
    _client.close();
  }
}