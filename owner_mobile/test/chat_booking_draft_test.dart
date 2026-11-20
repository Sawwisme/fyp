import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:owner_mobile/screens/chat_booking_flow.dart';
import 'package:owner_mobile/services/api_client.dart';
import 'package:owner_mobile/services/chatbot_service.dart';

import 'chat_booking_language_test.dart' show FakePets, fakeApi;
import 'chat_booking_typed_test.dart' show TypedAppointments;

Map<String, dynamic> clone(Map<String, dynamic> value) =>
    Map<String, dynamic>.from(jsonDecode(jsonEncode(value)) as Map);

const savedRequestId = 'b410d209-26c2-432a-a3f0-8996584f471e';

Map<String, dynamic> storedDraft({bool requested = false}) => {
  'schema_version': 1,
  'conversation_id': 1,
  'pet_context_id': 3,
  'state': {
    'step': requested ? 6 : 2,
    'pet': {'pet_id': 3, 'pet_name': 'Milo'},
    'clinic': {'clinic_id': 1, 'clinic_name': 'Willow Clinic'},
    'vet': {'veterinarian_id': 2, 'full_name': 'Dr Tan'},
    'slot': {
      'time_slot_id': 20,
      'start_time': '09:00:00',
      'end_time': '09:30:00',
    },
    'quote': {
      'clinic_id': 1,
      'version': 1,
      'deposit_amount': '0.00',
    },
    'type': 'dental_checkup',
    'date': DateTime.now()
        .add(const Duration(days: 2))
        .toIso8601String(),
    'request': requested ? {
      'pet_id': 3,
      'time_slot_id': 20,
      'appointment_type': 'dental_checkup',
      'booking_request_id': savedRequestId,
      'expected_payment_version': 1,
      'expected_deposit_amount': '0.00',
    } : null,
    'appointment_id': null,
    'history': <String>[],
  },
};

class SavedPets extends FakePets {
  @override
  Future<Map<String, dynamic>> getPet(int petId) async {
    if (petId != 3) {
      throw const ApiException('Pet not found.', statusCode: 404);
    }
    return {'pet_id': 3, 'pet_name': 'Milo'};
  }
}

class SavedAppointments extends TypedAppointments {
  @override
  Future<Map<String, dynamic>?> getMyAppointmentById(int id) async {
    return {
      'appointment_id': id,
      'pet_id': 3,
      'status': 'confirmed',
    };
  }
}

class SavedChat extends ChatbotService {
  SavedChat(this.draft) : super(fakeApi());

  Map<String, dynamic>? draft;
  int revision = 0;

  @override
  Future<Map<String, dynamic>> getConversation(int conversationId) async => {
    'conversation_id': conversationId,
    'pet_id': 3,
    'status': 'active',
    'booking_draft': draft == null ? null : clone(draft!),
    'booking_draft_revision': revision,
  };

  @override
  Future<Map<String, dynamic>> saveBookingDraft(
      int conversationId, {
        required int expectedRevision,
        required Map<String, dynamic>? draft,
      }) async {
    if (expectedRevision != revision) {
      throw const ApiException('Draft changed.', statusCode: 409);
    }
    this.draft = draft == null ? null : clone(draft);
    revision++;
    return getConversation(conversationId);
  }
}

Future<GlobalKey<ChatBookingFlowState>> mountBooking(
    WidgetTester tester,
    SavedChat chat,
    SavedAppointments appointments,
    ) async {
  final key = GlobalKey<ChatBookingFlowState>();

  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: SingleChildScrollView(
          child: ChatBookingFlow(
            key: key,
            chatbot: chat,
            conversationId: 1,
            initialPetId: 3,
            appointments: appointments,
            pets: SavedPets(),
            onOpenBookingPage: () {},
            onCancel: () {},
          ),
        ),
      ),
    ),
  );
  await tester.pumpAndSettle();
  return key;
}

void main() {
  setUp(() {});

  testWidgets('unfinished steps survive widget recreation', (tester) async {
    final chat = SavedChat(storedDraft());
    final appointments = SavedAppointments();

    final key = await mountBooking(tester, chat, appointments);
    expect(
      find.text('What type of appointment do you need?'),
      findsOneWidget,
    );

    await key.currentState!.handleTypedInput('1');
    await tester.pumpAndSettle();

    await mountBooking(tester, chat, appointments);
    expect(
      find.text('Which veterinarian would you prefer?'),
      findsOneWidget,
    );
    expect(find.text('Dr Tan'), findsOneWidget);
    expect(appointments.requestIds, isEmpty);
  });

  testWidgets('restored request needs explicit retry and keeps its ID',
          (tester) async {
        final chat = SavedChat(storedDraft(requested: true));
        final appointments = SavedAppointments();

        final key = await mountBooking(tester, chat, appointments);
        expect(appointments.requestIds, isEmpty);
        expect(find.text('Retry same booking'), findsOneWidget);

        // Cancellation must not discard an uncertain request.
        await key.currentState!.handleTypedInput('cancel');
        await tester.pumpAndSettle();
        expect(chat.draft!['state']['request']['booking_request_id'],
            savedRequestId);

        await key.currentState!.handleTypedInput('confirm booking');
        await tester.pumpAndSettle();
        expect(appointments.requestIds, [savedRequestId]);

        // Reopening a known appointment refreshes it without submitting again.
        await mountBooking(tester, chat, appointments);
        expect(find.text('Appointment #88 confirmed.'), findsOneWidget);
        expect(appointments.requestIds, [savedRequestId]);
      });

  testWidgets('wrong pet context cannot restore or submit', (tester) async {
    final draft = storedDraft();
    draft['pet_context_id'] = 999;

    final chat = SavedChat(draft);
    final appointments = SavedAppointments();

    await mountBooking(tester, chat, appointments);
    expect(
      find.textContaining(
        'Saved booking does not match this conversation.',
      ),
      findsOneWidget,
    );
    expect(appointments.requestIds, isEmpty);
    expect(chat.revision, 0);
  });

  testWidgets('closing an unsubmitted booking clears its saved draft',
          (tester) async {
        final chat = SavedChat(storedDraft());
        final appointments = SavedAppointments();

        final key = await mountBooking(tester, chat, appointments);
        await key.currentState!.handleTypedInput('cancel');
        await tester.pumpAndSettle();

        expect(chat.draft, isNull);
        expect(appointments.requestIds, isEmpty);
      });
}