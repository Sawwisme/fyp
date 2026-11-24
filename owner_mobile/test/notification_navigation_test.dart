import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:owner_mobile/screens/notifications.dart';
import 'package:owner_mobile/services/api_client.dart';
import 'package:owner_mobile/services/notification_service.dart';
import 'package:owner_mobile/services/token_storage.dart';

class FakeNotifications extends NotificationService {
  FakeNotifications(super.api);

  final requestedIds = <int>[];
  bool denyAccess = false;

  @override
  Future<List<Map<String, dynamic>>> getNotifications({
    int offset = 0,
    int limit = 21,
  }) async => [];

  @override
  Future<Map<String, dynamic>> getNotificationById(int id) async {
    requestedIds.add(id);

    if (denyAccess) {
      throw const ApiException(
        'Notification not found.',
        statusCode: 404,
      );
    }

    return {
      'notification_id': id,
      'resource_type': 'unknown_resource',
      'resource_id': 42,
      'title': 'Update',
      'message': 'Recorded update',
      'read_at': null,
    };
  }
}

void main() {
  late ApiClient api;
  late FakeNotifications notifications;

  setUp(() {
    api = ApiClient(tokenStorage: TokenStorage());
    notifications = FakeNotifications(api);
  });

  tearDown(() {
    api.close();
  });

  Future<void> openScreen(
      WidgetTester tester, {
        int? notificationId,
      }) async {
    await tester.pumpWidget(
      MaterialApp(
        home: OwnerNotificationsScreen(
          service: notifications,
          initialNotificationId: notificationId,
        ),
      ),
    );

    await tester.pumpAndSettle();
  }

  testWidgets('ordinary notification list does not open a record',
          (tester) async {
        await openScreen(tester);

        expect(notifications.requestedIds, isEmpty);
        expect(tester.takeException(), isNull);
      });

  testWidgets('banner target fetches the exact notification once',
          (tester) async {
        await openScreen(tester, notificationId: 73);

        expect(notifications.requestedIds, [73]);
        expect(
          find.text('This notification has no detail page.'),
          findsOneWidget,
        );

        await tester.pump();

        expect(notifications.requestedIds, [73]);
        expect(tester.takeException(), isNull);
      });

  testWidgets('denied notification displays an error',
          (tester) async {
        notifications.denyAccess = true;

        await openScreen(tester, notificationId: 74);

        expect(notifications.requestedIds, [74]);
        expect(
          find.textContaining('Could not open notification:'),
          findsOneWidget,
        );
        expect(
          find.text('This notification has no detail page.'),
          findsNothing,
        );
        expect(tester.takeException(), isNull);
      });
}