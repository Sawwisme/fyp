import 'api_client.dart';

class NotificationService {
  final ApiClient api;

  NotificationService(this.api);

  Future<List<Map<String, dynamic>>> getNotifications({
    int offset = 0,
    int limit = 21,
  }) async {
    final data = await api.get(
      '/notifications?offset=$offset&limit=$limit',
    );

    if (data is! List) {
      throw const ApiException('Invalid notification response.');
    }

    return data.map((item) {
      if (item is! Map) {
        throw const ApiException('Invalid notification record.');
      }

      return Map<String, dynamic>.from(item);
    }).toList();
  }

  Future<Map<String, dynamic>> markRead(int notificationId) async {
    final data = await api.post(
      '/notifications/$notificationId/read',
      {},
    );

    if (data is! Map) {
      throw const ApiException('Invalid notification response.');
    }

    return Map<String, dynamic>.from(data);
  }

  Future<int> getUnreadCount() async {
    final data = await api.get('/notifications/unread-count');

    if (data is! Map ||
        data['unread_count'] is! int ||
        (data['unread_count'] as int) < 0) {
      throw const ApiException('Invalid unread count.');
    }

    return data['unread_count'] as int;
  }

  Future<Map<String, dynamic>> getUpdates({int? afterId}) async {
    final query = afterId == null ? '' : '?after_id=$afterId';
    final data = await api.get('/notifications/updates$query');

    if (data is! Map ||
        data['items'] is! List ||
        data['cursor'] is! int ||
        (data['cursor'] as int) < 0) {
      throw const ApiException('Invalid notification update response.');
    }

    return Map<String, dynamic>.from(data);
  }
}