import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:owner_mobile/screens/chatbot.dart';
import 'package:owner_mobile/services/api_client.dart';
import 'package:owner_mobile/services/chatbot_service.dart';
import 'package:owner_mobile/services/token_storage.dart';

class FakeChatbotService extends ChatbotService {
  FakeChatbotService() : super(ApiClient(tokenStorage: TokenStorage()));

  final requests = <PendingChatMessage>[];
  bool failOnce = false;
  int nextId = 1;
  String language = 'en';

  @override
  Future<List<Map<String, dynamic>>> listConversations({
    int offset = 0,
    int limit = 20,
  }) async => [];

  @override
  Future<Map<String, dynamic>> createConversation({int? petId}) async => {
    'conversation_id': 1,
    'pet_id': petId,
    'pet_name': null,
    'status': 'active',
    'started_at': '2026-11-19T12:00:00Z',
  };

  @override
  Future<Map<String, dynamic>> sendMessage(
    int conversationId,
    PendingChatMessage pending,
  ) async {
    requests.add(pending);
    if (failOnce) {
      failOnce = false;
      throw const ApiException('Upload timed out. Retry the same message.');
    }
    if (pending.text == 'reply in chinese') language = 'zh';
    if (pending.text == 'reply in malay') language = 'ms';
    if (pending.text == 'reply in english') language = 'en';
    return {
      'messages': [
        {
          'message_id': nextId++,
          'sender_type': 'user',
          'message_text': pending.text,
          'response_metadata': <String, dynamic>{},
        },
        {
          'message_id': nextId++,
          'sender_type': 'assistant',
          'message_text': pending.text == 'change topic'
              ? 'Topic reset confirmed.'
              : 'Language preference saved.',
          'response_metadata': {
            'language': language,
            'intent': pending.text == 'change topic'
                ? 'conversation_reset'
                : 'language_preference',
            'mode': 'rule',
            'sources': <String>[],
            'products': <dynamic>[],
            'suggested_questions': <String>[],
            'recommended_action': 'NONE',
          },
        },
      ],
    };
  }
}

Finder messageInput() => find.byWidgetPredicate(
  (widget) => widget is TextField &&
      widget.decoration?.hintText == 'Message VetDental…',
);

Future<FakeChatbotService> openChat(
  WidgetTester tester, {
  bool mobile = false,
}) async {
  tester.view.devicePixelRatio = 1;
  tester.view.physicalSize = mobile
      ? const Size(390, 844)
      : const Size(1200, 900);
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  final service = FakeChatbotService();
  await tester.pumpWidget(MaterialApp(home: ChatbotScreen(service: service)));
  await tester.pumpAndSettle();
  return service;
}

void main() {
  testWidgets('language setting preserves the unsent draft', (tester) async {
    final service = await openChat(tester);
    await tester.enterText(messageInput(), 'My unsent question');
    await tester.tap(find.text('Language'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('中文'));
    await tester.pumpAndSettle();
    expect(service.requests.single.text, 'reply in chinese');
    expect(tester.widget<TextField>(messageInput()).controller!.text,
        'My unsent question');
    expect(find.text('中文'), findsOneWidget);
  });

  testWidgets('memory reset requires confirmation and retains history', (tester) async {
    final service = await openChat(tester);
    await tester.tap(find.text('Reset chat topic'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Close'));
    await tester.pumpAndSettle();
    expect(service.requests, isEmpty);
    await tester.tap(find.text('Reset chat topic'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Reset topic memory'));
    await tester.pumpAndSettle();
    expect(service.requests.single.text, 'change topic');
    expect(find.text('Topic reset confirmed.'), findsOneWidget);
    expect(find.text('change topic'), findsOneWidget);
  });

  testWidgets('uncertain settings retry reuses request ID and preserves draft', (tester) async {
    final service = await openChat(tester);
    service.failOnce = true;
    await tester.enterText(messageInput(), 'Keep this draft');
    await tester.tap(find.text('Language'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('中文'));
    await tester.pumpAndSettle();
    expect(service.requests, hasLength(1));
    await tester.tap(find.text('Retry'));
    await tester.pumpAndSettle();
    expect(service.requests, hasLength(2));
    expect(service.requests[0].requestId, service.requests[1].requestId);
    expect(tester.widget<TextField>(messageInput()).controller!.text, 'Keep this draft');
  });

  testWidgets('mobile drawer exposes language and memory controls', (tester) async {
    await openChat(tester, mobile: true);
    await tester.tap(find.byTooltip('Chat history'));
    await tester.pumpAndSettle();
    expect(find.text('Language'), findsOneWidget);
    expect(find.text('Reset chat topic'), findsOneWidget);
    await tester.tap(find.text('Language'));
    await tester.pumpAndSettle();
    expect(find.text('Reply language'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
