import 'package:flutter/material.dart';

import '../services/api_client.dart';
import '../services/appointment_service.dart';
import '../services/chatbot_service.dart';
import '../services/pet_service.dart';
import 'booking_payment.dart';

class ChatBookingFlow extends StatefulWidget {
  final AppointmentService appointments;
  final PetService pets;
  final VoidCallback onOpenBookingPage;
  final VoidCallback onCancel;

  const ChatBookingFlow({
    super.key,
    required this.appointments,
    required this.pets,
    required this.onOpenBookingPage,
    required this.onCancel,
  });

  @override
  State<ChatBookingFlow> createState() => _ChatBookingFlowState();
}

class _ChatBookingFlowState extends State<ChatBookingFlow> with AutomaticKeepAliveClientMixin<ChatBookingFlow> {
  @override
  bool get wantKeepAlive => true;
  static const _blue = Color(0xFF2549C7);

  final _history = <String>[];
  List<Map<String, dynamic>> _choices = [];

  Map<String, dynamic>? _pet;
  Map<String, dynamic>? _clinic;
  Map<String, dynamic>? _vet;
  Map<String, dynamic>? _slot;
  Map<String, dynamic>? _quote;
  Map<String, dynamic>? _request;
  Map<String, dynamic>? _appointment;

  DateTime? _date;
  String? _type;

  int _step = 0;
  bool _busy = true;
  bool _uncertain = false;
  String? _error;

  static const _questions = [
    'Which pet is the appointment for?',
    'Which clinic would you like to visit?',
    'What type of appointment do you need?',
    'Which veterinarian would you prefer?',
    'Which date would you like?',
    'Choose an available appointment time.',
    'Please review your appointment before confirming.',
  ];

  @override
  void initState() {
    super.initState();
    _loadStep();
  }

  Future<List<Map<String, dynamic>>> _allPages(
      Future<List<Map<String, dynamic>>> Function(int offset) fetch,
      ) async {
    final items = <Map<String, dynamic>>[];

    for (var offset = 0; ; offset += 100) {
      final page = await fetch(offset);
      items.addAll(page);

      if (page.length < 100) return items;
    }
  }

  DateTime _today() {
    final now = DateTime.now().toUtc().add(
      const Duration(hours: 8),
    );
    return DateTime(now.year, now.month, now.day);
  }

  String _dateLabel(DateTime date) {
    return '${date.day.toString().padLeft(2, '0')}/'
        '${date.month.toString().padLeft(2, '0')}/'
        '${date.year}';
  }

  String _timeLabel(Map<String, dynamic> slot) {
    String short(dynamic value) {
      final text = '$value';
      return text.length >= 5 ? text.substring(0, 5) : text;
    }

    return '${short(slot['start_time'])}–'
        '${short(slot['end_time'])}';
  }

  Future<void> _loadStep() async {
    setState(() {
      _busy = true;
      _error = null;
      _choices = [];
    });

    try {
      List<Map<String, dynamic>> choices = [];

      switch (_step) {
        case 0:
          choices = await _allPages(
                (offset) => widget.pets.getPets(
              offset: offset,
              limit: 100,
            ),
          );
          break;

        case 1:
          choices = await _allPages(
                (offset) => widget.appointments.getClinics(
              offset: offset,
              limit: 100,
            ),
          );
          break;

        case 2:
          choices = [
            {'value': 'dental_checkup', 'label': 'Dental checkup'},
            {'value': 'consultation', 'label': 'Consultation'},
          ];
          break;

        case 3:
          choices = await _allPages(
                (offset) => widget.appointments.getVeterinarians(
              clinicId: _clinic!['clinic_id'] as int,
              offset: offset,
              limit: 100,
            ),
          );
          break;

        case 5:
          choices = await _allPages(
                (offset) => widget.appointments.getAvailableSlots(
              veterinarianId: _vet!['veterinarian_id'] as int,
              date: _date!,
              offset: offset,
              limit: 100,
            ),
          );
          break;

        case 6:
          final quote =
          await widget.appointments.getBookingPaymentQuote(
            _clinic!['clinic_id'] as int,
          );

          if (!mounted) return;
          _quote = quote;
          break;
      }

      if (!mounted) return;
      setState(() => _choices = choices);
    } catch (error) {
      if (mounted) {
        setState(() {
          _error = error is ApiException
              ? error.message
              : 'Could not load booking choices. Please try again.';
        });
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  String _choiceLabel(Map<String, dynamic> item) {
    switch (_step) {
      case 0:
        return '${item['pet_name']}';
      case 1:
        return '${item['clinic_name']}';
      case 2:
        return '${item['label']}';
      case 3:
        return '${item['full_name']}';
      case 5:
        return _timeLabel(item);
      default:
        return '';
    }
  }

  Future<void> _choose(Map<String, dynamic> item) async {
    if (_busy || _request != null || _appointment != null) return;

    final answer = _choiceLabel(item);

    switch (_step) {
      case 0:
        _pet = item;
        break;
      case 1:
        _clinic = item;
        break;
      case 2:
        _type = item['value'] as String;
        break;
      case 3:
        _vet = item;
        break;
      case 5:
        _slot = item;
        break;
    }

    setState(() {
      _history.add('${_questions[_step]}\n$answer');
      _step++;
    });

    await _loadStep();
  }

  Future<void> _chooseDate() async {
    if (_busy || _request != null) return;

    final today = _today();

    final date = await showDatePicker(
      context: context,
      initialDate: today,
      firstDate: today,
      lastDate: today.add(const Duration(days: 90)),
    );

    if (!mounted || date == null) return;

    setState(() {
      _date = date;
      _history.add('${_questions[4]}\n${_dateLabel(date)}');
      _step = 5;
    });

    await _loadStep();
  }

  Future<void> _back() async {
    if (_busy || _request != null || _step == 0) return;

    setState(() {
      _step--;
      if (_history.isNotEmpty) _history.removeLast();
      _quote = null;
      _error = null;
    });

    await _loadStep();
  }

  Future<void> _confirm() async {
    if (_busy || _quote == null || _appointment != null) return;

    // Freeze the request. An uncertain retry must use the same ID
    // and exactly the same booking details.
    _request ??= {
      'pet_id': _pet!['pet_id'],
      'time_slot_id': _slot!['time_slot_id'],
      'appointment_type': _type,
      'booking_request_id':
      PendingChatMessage('Appointment booking').requestId,
      'expected_payment_version': _quote!['version'],
      'expected_deposit_amount':
      _quote!['deposit_amount'].toString(),
    };

    setState(() {
      _busy = true;
      _error = null;
    });

    try {
      final request = _request!;

      final appointment = await widget.appointments.createAppointment(
        petId: request['pet_id'] as int,
        timeSlotId: request['time_slot_id'] as int,
        appointmentType: request['appointment_type'] as String,
        bookingRequestId: request['booking_request_id'] as String,
        expectedPaymentVersion:
        request['expected_payment_version'] as int,
        expectedDepositAmount:
        request['expected_deposit_amount'] as String,
      );

      if (!mounted) return;

      setState(() {
        _appointment = appointment;
        _uncertain = false;
      });
    } catch (error) {
      if (!mounted) return;

      final status = error is ApiException ? error.statusCode : null;

      // Only known validation/rejection responses permit a new request.
      final rejected = {400, 403, 404, 409, 422}.contains(status);

      setState(() {
        _uncertain = !rejected;

        if (rejected) {
          _request = null;
          _quote = null;
        }

        _error = _uncertain
            ? 'The booking response could not be confirmed. '
            'Tap Retry same booking before making another booking.'
            : error is ApiException
            ? error.message
            : 'The booking could not be created.';
      });
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _openPayment() async {
    final appointment = _appointment;
    if (_busy || appointment == null) return;

    final appointmentId = appointment['appointment_id'] as int;

    setState(() => _busy = true);

    try {
      await Navigator.of(context).push<void>(
        MaterialPageRoute(
          builder: (_) => BookingPaymentScreen(
            service: widget.appointments,
            appointmentId: appointmentId,
            onStatusChanged: (data) {
              if (!mounted ||
                  data['appointment_id'] != appointmentId ||
                  _appointment?['appointment_id'] != appointmentId) {
                return;
              }

              final status = data['appointment_status'];
              if (status is! String) return;

              setState(() {
                _appointment = {
                  ..._appointment!,
                  'status': status,
                  'payment_status': data['payment_status'],
                  'checkout_status': data['checkout_status'],
                };
              });
            },
          ),
        ),
      );
    } finally {
      if (mounted) {
        setState(() => _busy = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final appointment = _appointment;
    super.build(context);

    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(top: 12, bottom: 16),
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: const Color(0xFFDCE2ED)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              const Icon(
                Icons.calendar_month_rounded,
                color: _blue,
              ),
              const SizedBox(width: 10),
              const Expanded(
                child: Text(
                  'Appointment assistant',
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
              IconButton(
                tooltip: appointment != null
                    ? 'Close booking summary'
                    : 'Cancel booking steps',
                onPressed: _busy || (_request != null && appointment == null)
                    ? null
                    : widget.onCancel,
                icon: const Icon(Icons.close_rounded),
              ),
            ],
          ),
          const SizedBox(height: 16),

          for (final answer in _history)
            Container(
              margin: const EdgeInsets.only(bottom: 10),
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: const Color(0xFFF2F5FC),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Text(answer),
            ),

          if (appointment != null) ...[
            Text(
              switch (appointment['status']) {
                'confirmed' =>
                'Appointment #${appointment['appointment_id']} confirmed.',
                'pending_payment' =>
                'Appointment #${appointment['appointment_id']} is awaiting payment.',
                'cancelled' =>
                'Appointment #${appointment['appointment_id']} was cancelled.',
                'completed' =>
                'Appointment #${appointment['appointment_id']} is completed.',
                _ =>
                'Appointment #${appointment['appointment_id']}: '
                    '${appointment['status'].toString().replaceAll('_', ' ')}.',
              },
              style: const TextStyle(fontWeight: FontWeight.w700),
            ),
            if (appointment['status'] == 'pending_payment') ...[
              const SizedBox(height: 8),
              const Text(
                'Complete the deposit payment to confirm your appointment. '
                    'If you already paid, open payment status to check it.',
              ),
              const SizedBox(height: 12),
              FilledButton(
                onPressed: _busy ? null : _openPayment,
                child: const Text('Pay deposit / check payment status'),
              ),
            ],
          ] else ...[
            Text(
              _questions[_step],
              style: const TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 12),

            if (_busy)
              const LinearProgressIndicator()
            else if (_error == null) ...[
              if (_step == 4)
                OutlinedButton.icon(
                  onPressed: _chooseDate,
                  icon: const Icon(Icons.calendar_today_outlined),
                  label: const Text('Choose date'),
                )
              else if (_step == 6 && _quote != null) ...[
                Text(
                  'Deposit: RM '
                      '${num.parse('${_quote!['deposit_amount']}').toStringAsFixed(2)}',
                  style: const TextStyle(fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 8),
                const Text(
                  'All appointment times use Malaysia time. '
                      'Any deposit is deducted from the final consultation bill.',
                ),
                const SizedBox(height: 12),
                FilledButton(
                  onPressed: _confirm,
                  child: const Text('Confirm booking'),
                ),
              ] else if (_choices.isEmpty)
                Text(
                  _step == 5
                      ? 'No slots are available. Go back and choose another date.'
                      : 'No choices are available. Go back or use the booking page.',
                )
              else
                for (final choice in _choices)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: OutlinedButton(
                      onPressed: () => _choose(choice),
                      child: Text(_choiceLabel(choice)),
                    ),
                  ),
            ],

            if (_error != null) ...[
              Text(
                _error!,
                style: const TextStyle(color: Color(0xFFB42318)),
              ),
              TextButton(
                onPressed: _busy
                    ? null
                    : _uncertain
                    ? _confirm
                    : () => _loadStep(),
                child: Text(
                  _uncertain ? 'Retry same booking' : 'Reload choices',
                ),
              ),
            ],

            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                if (_step > 0)
                  TextButton(
                    onPressed: _busy || _request != null ? null : _back,
                    child: const Text('Back'),
                  ),
                TextButton(
                  onPressed: _busy || _request != null
                      ? null
                      : widget.onOpenBookingPage,
                  child: const Text('Open booking page instead'),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}