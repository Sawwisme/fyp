import 'api_client.dart';

class AppointmentService {
  final ApiClient api;

  AppointmentService(this.api);

  String _dateOnly(DateTime date) {
    final year = date.year.toString().padLeft(4, '0');
    final month = date.month.toString().padLeft(2, '0');
    final day = date.day.toString().padLeft(2, '0');

    return '$year-$month-$day';
  }

  List<Map<String, dynamic>> _readList(dynamic data) {
    if (data is! List) {
      throw const ApiException('Invalid server list response.');
    }

    return data.map((item) {
      if (item is! Map<String, dynamic>) {
        throw const ApiException('Invalid server record.');
      }

      return item;
    }).toList();
  }

  Future<List<Map<String, dynamic>>> getVeterinarians({
    int? clinicId,
    int offset = 0,
    int limit = 100,
  }) async {
    final query = Uri(
      queryParameters: {
        if (clinicId != null) 'clinic_id': '$clinicId',
        'offset': '$offset',
        'limit': '$limit',
      },
    ).query;

    final data = await api.get(
      '/availability/veterinarians?$query',
    );

    return _readList(data);
  }

  Future<List<Map<String, dynamic>>> getAvailableSlots({
    required int veterinarianId,
    required DateTime date,
    int offset = 0,
    int limit = 100,
  }) async {
    final query = Uri(
      queryParameters: {
        'appointment_date': _dateOnly(date),
        'offset': '$offset',
        'limit': '$limit',
      },
    ).query;

    final data = await api.get(
      '/availability/veterinarians/$veterinarianId/slots?$query',
    );

    return _readList(data);
  }

  Future<Map<String, dynamic>> createAppointment({
    required int petId,
    required int timeSlotId,
    required String appointmentType,
    int? followupCareId,
    String? bookingRequestId,
    int? expectedPaymentVersion,
    String? expectedDepositAmount,
  }) async {
    final body = <String, dynamic>{
      'pet_id': petId,
      'time_slot_id': timeSlotId,
      'appointment_type': appointmentType,
    };

    if (followupCareId != null) {
      body['followup_care_id'] = followupCareId;
    }

    if (bookingRequestId != null) {
      if (expectedPaymentVersion == null ||
          expectedDepositAmount == null) {
        throw const ApiException(
          'Confirm the deposit amount before booking.',
          statusCode: 422,
        );
      }

      body['booking_request_id'] = bookingRequestId;
      body['expected_payment_version'] = expectedPaymentVersion;
      body['expected_deposit_amount'] = expectedDepositAmount;
    }

    final data = await api.post(
      '/owner-appointments',
      body,
    );

    if (data is! Map ||
        data['appointment_id'] is! int ||
        data['status'] is! String) {
      throw const ApiException(
        'Could not confirm the booking response. '
            'Check the existing booking before trying again.',
      );
    }

    return Map<String, dynamic>.from(data);
  }

  Future<List<Map<String, dynamic>>> getMyAppointments({
    DateTime? date,
    int offset = 0,
    int limit = 20,
  }) async {
    final query = Uri(
      queryParameters: {
        if (date != null) 'appointment_date': _dateOnly(date),
        'offset': '$offset',
        'limit': '$limit',
      },
    ).query;

    final data = await api.get('/owner-appointments?$query');

    return _readList(data);
  }

  Future<List<Map<String, dynamic>>> getClinics({
    int offset = 0,
    int limit = 100,
  }) async {
    final query = Uri(
      queryParameters: {
        'offset': '$offset',
        'limit': '$limit',
      },
    ).query;

    final data = await api.get('/availability/clinics?$query');

    return _readList(data);
  }

  Future<Map<String, dynamic>> submitEmergencyRequest({
    required int clinicId,
    required int petId,
    required String reason,
  }) async {
    dynamic data;

    try {
      data = await api.post(
        '/emergency-requests',
        {
          'clinic_id': clinicId,
          'pet_id': petId,
          'emergency_reason': reason.trim(),
        },
      );
    } on ApiException catch (error) {
      if (error.statusCode == null ||
          (error.statusCode != null && error.statusCode! >= 500)) {
        throw const ApiException(
          'Could not confirm submission. Check your emergency '
              'requests before trying again.',
        );
      }

      rethrow;
    }

    if (data is! Map<String, dynamic>) {
      throw const ApiException(
        'Could not confirm submission. Check your emergency '
            'requests before trying again.',
      );
    }

    return data;
  }

  Future<List<Map<String, dynamic>>> getMyEmergencyRequests({
    int offset = 0,
    int limit = 20,
  }) async {
    final query = Uri(
      queryParameters: {
        'offset': '$offset',
        'limit': '$limit',
      },
    ).query;

    final data = await api.get('/emergency-requests/mine?$query');

    return _readList(data);
  }

  Future<void> cancelEmergencyRequest(int requestId) async {
    try {
      await api.post(
        '/emergency-requests/$requestId/cancel',
        {},
      );
    } on ApiException catch (error) {
      if (error.statusCode == null ||
          (error.statusCode != null && error.statusCode! >= 500)) {
        throw const ApiException(
          'Could not confirm cancellation. '
              'Refresh your requests to check the latest status.',
        );
      }

      rethrow;
    }
  }

  Future<void> cancelAppointment(int appointmentId) async {
    try {
      await api.post(
        '/owner-appointments/$appointmentId/cancel',
        {},
      );
    } on ApiException catch (error) {
      if (error.statusCode == null ||
          (error.statusCode != null && error.statusCode! >= 500)) {
        throw const ApiException(
          'Could not confirm cancellation. '
              'Refresh My Appointments to check the latest status.',
        );
      }

      rethrow;
    }
  }

  Future<void> rescheduleAppointment({
    required int appointmentId,
    required int timeSlotId,
  }) async {
    try {
      final data = await api.post(
        '/owner-appointments/$appointmentId/reschedule',
        {'time_slot_id': timeSlotId},
      );

      if (data is! Map<String, dynamic>) {
        throw const ApiException(
          'Could not confirm the change. '
              'Check My Appointments before trying again.',
        );
      }
    } on ApiException catch (error) {
      if (error.statusCode == null ||
          (error.statusCode != null && error.statusCode! >= 500)) {
        throw const ApiException(
          'Could not confirm the change. '
              'Check My Appointments before trying again.',
        );
      }

      rethrow;
    }
  }

  Future<Map<String, dynamic>?> getAppointmentRecord(
      int appointmentId,
      ) async {
    final data = await api.get(
      '/owner-medical-history/appointments/$appointmentId',
    );

    if (data == null) return null;

    if (data is! Map<String, dynamic>) {
      throw const ApiException('Invalid medical record response.');
    }

    return data;
  }

  Future<Map<String, dynamic>> getBookingPaymentQuote(
      int clinicId,
      ) async {
    final data = await api.get(
      '/owner-appointments/clinics/$clinicId/payment-quote',
    );

    if (data is! Map ||
        data['clinic_id'] != clinicId ||
        data['version'] is! int ||
        (data['version'] as int) < 1) {
      throw const ApiException('Invalid booking payment quote.');
    }

    final amount = num.tryParse(
      data['deposit_amount']?.toString() ?? '',
    );

    if (amount == null ||
        !amount.isFinite ||
        amount < 0 ||
        amount > 30000 ||
        (amount > 0 && amount < 1)) {
      throw const ApiException('Invalid booking deposit amount.');
    }

    return Map<String, dynamic>.from(data);
  }

  Future<Map<String, dynamic>> openBookingCheckout(
      int appointmentId,
      ) async {
    final data = await api.post(
      '/owner-appointments/$appointmentId/checkout',
      {},
    );

    if (data is! Map ||
        data['appointment_id'] != appointmentId ||
        data['appointment_status'] is! String ||
        data['payment_status'] is! String ||
        data['checkout_status'] is! String ||
        (data['checkout_url'] != null &&
            data['checkout_url'] is! String)) {
      throw const ApiException('Invalid booking payment response.');
    }

    return Map<String, dynamic>.from(data);
  }
}