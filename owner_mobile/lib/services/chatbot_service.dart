import 'dart:math';

import 'api_client.dart';

/// Keep this object when retrying a message.
/// Reusing its request ID prevents duplicate messages.
class PendingChatMessage {
  final String requestId;
  final String text;

  PendingChatMessage(String message)
      : requestId = _newRequestId(),
        text = message.trim() {
    if (text.isEmpty || text.length > 2000) {
      throw ArgumentError(
        'Enter a message between 1 and 2000 characters.',
      );
    }
  }

  static String _newRequestId() {
    final random = Random.secure();
    final bytes = List<int>.generate(
      16,
          (_) => random.nextInt(256),
    );

    // UUID version 4.
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;

    final hex = bytes
        .map((value) => value.toRadixString(16).padLeft(2, '0'))
        .join();

    return '${hex.substring(0, 8)}-'
        '${hex.substring(8, 12)}-'
        '${hex.substring(12, 16)}-'
        '${hex.substring(16, 20)}-'
        '${hex.substring(20)}';
  }
}

class ChatbotService {
  final ApiClient api;

  ChatbotService(this.api);

  Map<String, dynamic> _asMap(dynamic value) {
    if (value is! Map<String, dynamic>) {
      throw const ApiException(
        'The server returned an unexpected chatbot response.',
      );
    }

    return value;
  }

  Future<List<Map<String, dynamic>>> listConversations({
    int offset = 0,
    int limit = 20,
  }) async {
    final data = await api.get(
      '/chatbot/conversations?offset=$offset&limit=$limit',
    );

    if (data is! List) {
      throw const ApiException(
        'The server returned an unexpected chat list.',
      );
    }

    return data.map(_asMap).toList();
  }

  Future<Map<String, dynamic>> createConversation({
    int? petId,
  }) async {
    final data = await api.post(
      '/chatbot/conversations',
      {
        'pet_id': ?petId,
      },
    );

    return _asMap(data);
  }

  Future<Map<String, dynamic>> getConversation(
      int conversationId,
      ) async {
    final data = await api.get(
      '/chatbot/conversations/$conversationId',
    );

    return _asMap(data);
  }

  /// Returns items in chronological order.
  /// Use next_before_message_id to load older messages.
  Future<Map<String, dynamic>> listMessages(
      int conversationId, {
        int? beforeMessageId,
        int limit = 50,
      }) async {
    final query = Uri(
      queryParameters: {
        'limit': '$limit',
        if (beforeMessageId != null)
          'before_message_id': '$beforeMessageId',
      },
    ).query;

    final data = await api.get(
      '/chatbot/conversations/$conversationId/messages?$query',
    );

    final result = _asMap(data);

    if (result['items'] is! List ||
        result['has_more'] is! bool) {
      throw const ApiException(
        'The server returned an unexpected message history.',
      );
    }

    return result;
  }

  Future<Map<String, dynamic>> sendMessage(
      int conversationId,
      PendingChatMessage pending,
      ) async {
    final data = await api.post(
      '/chatbot/conversations/$conversationId/messages',
      {
        'client_request_id': pending.requestId,
        'message': pending.text,
      },
    );

    final result = _asMap(data);

    if (result['messages'] is! List) {
      throw const ApiException(
        'The server returned an unexpected message response.',
      );
    }

    return result;
  }

  Future<Map<String, dynamic>> closeConversation(
      int conversationId,
      ) async {
    final data = await api.post(
      '/chatbot/conversations/$conversationId/close',
      {},
    );

    return _asMap(data);
  }

  Future<Map<String, dynamic>> saveBookingDraft(
      int conversationId, {
        required int expectedRevision,
        required Map<String, dynamic>? draft,
      }) async {
    final data = await api.put(
      '/chatbot/conversations/$conversationId/booking-draft',
      {
        'expected_revision': expectedRevision,
        'draft': draft,
      },
    );

    final result = _asMap(data);

    if (result['conversation_id'] != conversationId ||
        result['booking_draft_revision'] is! int) {
      throw const ApiException(
        'The server returned an invalid booking draft response.',
      );
    }

    return result;
  }
}