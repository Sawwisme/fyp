import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:owner_mobile/screens/chat_booking_flow.dart';
import 'package:owner_mobile/services/api_client.dart';
import 'package:owner_mobile/services/appointment_service.dart';
import 'package:owner_mobile/services/pet_service.dart';
import 'package:owner_mobile/services/token_storage.dart';

ApiClient fakeApi() => ApiClient(tokenStorage: TokenStorage());

class FakePets extends PetService {
  FakePets() : super(fakeApi());

  @override
  Future<List<Map<String, dynamic>>> getPets({
    int offset = 0,
    int limit = 20,
  }) async => [
    {'pet_id': 3, 'pet_name': 'Milo'},
  ];
}

class FakeAppointments extends AppointmentService {
  FakeAppointments() : super(fakeApi());

  @override
  Future<List<Map<String, dynamic>>> getClinics({
    int offset = 0,
    int limit = 100,
  }) async => [
    {'clinic_id': 1, 'clinic_name': 'Willow Clinic'},
  ];

  @override
  Future<List<Map<String, dynamic>>> getVeterinarians({
    int? clinicId,
    int offset = 0,
    int limit = 100,
  }) async => [
    {'veterinarian_id': 2, 'full_name': 'Dr Tan'},
  ];
}

void main() {
  const cases = {
    'en': [
      'Which pet is the appointment for?',
      'Dental checkup',
      'Choose date',
    ],
    'ms': [
      'Janji temu ini untuk haiwan yang mana?',
      'Pemeriksaan pergigian',
      'Pilih tarikh',
    ],
    'zh': [
      '这次预约是为哪只宠物安排的？',
      '牙齿检查',
      '选择日期',
    ],
  };

  for (final entry in cases.entries) {
    testWidgets(
      '${entry.key}: booking labels and calendar locale',
          (tester) async {
        tester.view.devicePixelRatio = 1;
        tester.view.physicalSize = const Size(1200, 1600);
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);

        await tester.pumpWidget(
          MaterialApp(
            localizationsDelegates:
            GlobalMaterialLocalizations.delegates,
            supportedLocales: const [
              Locale('en'),
              Locale('ms'),
              Locale('zh', 'CN'),
            ],
            home: Scaffold(
              body: SingleChildScrollView(
                child: ChatBookingFlow(
                  language: entry.key,
                  appointments: FakeAppointments(),
                  pets: FakePets(),
                  onOpenBookingPage: () {},
                  onCancel: () {},
                ),
              ),
            ),
          ),
        );

        await tester.pumpAndSettle();
        expect(find.text(entry.value[0]), findsOneWidget);

        await tester.tap(find.text('Milo'));
        await tester.pumpAndSettle();

        // Actual names remain unchanged.
        expect(find.text('Willow Clinic'), findsOneWidget);
        await tester.tap(find.text('Willow Clinic'));
        await tester.pumpAndSettle();

        expect(find.text(entry.value[1]), findsOneWidget);
        await tester.tap(find.text(entry.value[1]));
        await tester.pumpAndSettle();

        expect(find.text('Dr Tan'), findsOneWidget);
        await tester.tap(find.text('Dr Tan'));
        await tester.pumpAndSettle();

        final dateButton = find.text(entry.value[2]);
        await tester.ensureVisible(dateButton);
        await tester.tap(dateButton);
        await tester.pumpAndSettle();

        final calendar = find.byType(DatePickerDialog);
        expect(calendar, findsOneWidget);
        expect(
          Localizations.localeOf(tester.element(calendar)).languageCode,
          entry.key,
        );
        expect(tester.takeException(), isNull);
      },
    );
  }

  testWidgets('chat pet skips pet selection', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: ChatBookingFlow(
              initialPetId: 3,
              appointments: FakeAppointments(),
              pets: FakePets(),
              onOpenBookingPage: () {},
              onCancel: () {},
            ),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(
      find.text('Which clinic would you like to visit?'),
      findsOneWidget,
    );
    expect(find.text('Willow Clinic'), findsOneWidget);

    // Milo appears in the history, not as a pet-selection button.
    expect(
      find.widgetWithText(OutlinedButton, 'Milo'),
      findsNothing,
    );
    expect(tester.takeException(), isNull);
  });

  testWidgets('unavailable chat pet cannot silently change', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: ChatBookingFlow(
              initialPetId: 999,
              appointments: FakeAppointments(),
              pets: FakePets(),
              onOpenBookingPage: () {},
              onCancel: () {},
            ),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(
      find.textContaining(
        'The pet linked to this chat is unavailable.',
      ),
      findsOneWidget,
    );
    expect(find.text('Willow Clinic'), findsNothing);
    expect(
      find.widgetWithText(OutlinedButton, 'Milo'),
      findsNothing,
    );
    expect(tester.takeException(), isNull);
  });
}