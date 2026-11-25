import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:owner_mobile/screens/chat_booking_flow.dart';

import 'chat_booking_language_test.dart'
    show FakeAppointments, FakePets;

class TypedAppointments extends FakeAppointments {
  final requestIds = <String?>[];

  @override
  Future<List<Map<String, dynamic>>> getAvailableSlots({
    required int veterinarianId,
    required DateTime date,
    int offset = 0,
    int limit = 100,
  }) async => [
    {
      'time_slot_id': 20,
      'start_time': '09:00:00',
      'end_time': '09:30:00',
    },
  ];

  @override
  Future<Map<String, dynamic>> getBookingPaymentQuote(
      int clinicId,
      ) async => {
    'clinic_id': clinicId,
    'version': 1,
    'deposit_amount': '0.00',
  };

  @override
  Future<Map<String, dynamic>> createAppointment({
    required int petId,
    required int timeSlotId,
    required String appointmentType,
    int? followupCareId,
    int? aiAssessmentReviewId,
    String? bookingRequestId,
    int? aiAnalysisId,
    bool shareAiAssessment = false,
    int? expectedPaymentVersion,
    bool shareMedicalHistory = false,
    String? expectedDepositAmount,
  }) async {
    requestIds.add(bookingRequestId);
    return {
      'appointment_id': 88,
      'pet_id': petId,
      'status': 'confirmed',
    };
  }
}

Future<GlobalKey<ChatBookingFlowState>> openTypedBooking(
    WidgetTester tester,
    TypedAppointments appointments, {
      String language = 'en',
      VoidCallback? onCancel,
    }) async {
  tester.view.devicePixelRatio = 1;
  tester.view.physicalSize = const Size(1200, 1600);
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);

  final key = GlobalKey<ChatBookingFlowState>();

  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: SingleChildScrollView(
          child: ChatBookingFlow(
            key: key,
            initialPetId: 3,
            language: language,
            appointments: appointments,
            pets: FakePets(),
            onOpenBookingPage: () {},
            onCancel: onCancel ?? () {},
          ),
        ),
      ),
    ),
  );
  await tester.pumpAndSettle();
  return key;
}

void main() {
  for (final entry in {
    'en': ['tomorrow', 'confirm booking'],
    'ms': ['esok', 'sahkan janji temu'],
    'zh': ['明天', '确认预约'],
  }.entries) {
    testWidgets(
      '${entry.key}: typed choices require explicit confirmation',
          (tester) async {
        final appointments = TypedAppointments();
        final key = await openTypedBooking(
          tester,
          appointments,
          language: entry.key,
        );

        Future<void> answer(String text) async {
          expect(
            await key.currentState!.handleTypedInput(text),
            isTrue,
          );
          await tester.pumpAndSettle();
        }

        await answer('1'); // Clinic.
        await answer('1'); // Appointment type.
        await answer('1'); // Vet.
        await answer(entry.value[0]); // Date.
        await answer('1'); // Slot.

        expect(appointments.requestIds, isEmpty);

        // A casual acknowledgement must not create a booking.
        expect(
          await key.currentState!.handleTypedInput('yes'),
          isFalse,
        );
        expect(appointments.requestIds, isEmpty);

        // Two simultaneous confirmations must submit only once.
        await Future.wait([
          key.currentState!.handleTypedInput(entry.value[1]),
          key.currentState!.handleTypedInput(entry.value[1]),
        ]);
        await tester.pumpAndSettle();

        expect(appointments.requestIds, hasLength(1));
        expect(appointments.requestIds.single, isNotEmpty);
      },
    );
  }

  testWidgets('unrelated safety message reaches the chatbot', (tester) async {
    final appointments = TypedAppointments();
    final key = await openTypedBooking(tester, appointments);

    expect(
      await key.currentState!.handleTypedInput(
        'my cat cannot breathe',
      ),
      isFalse,
    );
    expect(appointments.requestIds, isEmpty);
  });

  for (final commands in [
    ['back', 'restart', 'cancel'],
    ['kembali', 'mula semula', 'batal'],
    ['返回', '重新开始', '取消'],
  ]) {
    testWidgets('${commands.first}: navigation commands', (tester) async {
      final appointments = TypedAppointments();
      var cancelled = false;
      final key = await openTypedBooking(
        tester,
        appointments,
        onCancel: () => cancelled = true,
      );

      await key.currentState!.handleTypedInput('1');
      await tester.pumpAndSettle();

      expect(
        await key.currentState!.handleTypedInput(commands[0]),
        isTrue,
      );
      await tester.pumpAndSettle();
      expect(
        find.text('Which clinic would you like to visit?'),
        findsOneWidget,
      );

      expect(
        await key.currentState!.handleTypedInput(commands[1]),
        isTrue,
      );
      await tester.pumpAndSettle();

      expect(
        await key.currentState!.handleTypedInput(commands[2]),
        isTrue,
      );
      expect(cancelled, isTrue);
      expect(appointments.requestIds, isEmpty);
    });
  }
}