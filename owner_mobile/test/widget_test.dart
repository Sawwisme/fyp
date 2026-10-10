// This is a basic Flutter widget test.
//
// To perform an interaction with a widget in your test, use the WidgetTester
// utility in the flutter_test package. For example, you can send tap and scroll
// gestures. You can also use WidgetTester to find child widgets in the widget
// tree, read text, and verify that the values of widget properties are correct.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:owner_mobile/screens/login.dart';
import 'package:owner_mobile/services/api_client.dart';
import 'package:owner_mobile/services/auth_service.dart';
import 'package:owner_mobile/services/token_storage.dart';

void main() {
  testWidgets('Login requires email and password', (tester) async {
    final api = ApiClient(tokenStorage: TokenStorage());
    addTearDown(api.close);

    await tester.pumpWidget(
      MaterialApp(
        home: LoginScreen(
          auth: AuthService(api),
          onLoggedIn: (_) {},
        ),
      ),
    );

    expect(find.text('Welcome back'), findsOneWidget);

    await tester.tap(find.widgetWithText(FilledButton, 'Log in'));
    await tester.pump();

    expect(find.text('Enter your email'), findsOneWidget);
    expect(find.text('Enter your password'), findsOneWidget);
  });
}