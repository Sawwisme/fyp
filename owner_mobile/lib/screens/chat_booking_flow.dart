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
  final String language;
  final int? initialPetId;
  final ChatbotService? chatbot;
  final int? conversationId;

  const ChatBookingFlow({
    super.key,
    required this.appointments,
    required this.pets,
    required this.onOpenBookingPage,
    required this.onCancel,
    this.language = 'en',
    this.initialPetId,
    this.chatbot,
    this.conversationId,
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

  int _draftRevision = 0;
  bool _draftReady = false;

  bool get _usesDraftStorage =>
      widget.chatbot != null && widget.conversationId != null;

  String get _resumeWarning => _text(
    'An unfinished booking request was restored. '
        'Retry the same booking to check its outcome.',
    'Permintaan janji temu belum selesai telah dipulihkan. '
        'Cuba semula janji temu yang sama untuk menyemak keputusannya.',
    '已恢复尚未确认结果的预约请求。'
        '请重试同一预约以检查结果。',
  );

  Map<String, dynamic> _draftPayload() => {
    'schema_version': 1,
    'conversation_id': widget.conversationId,
    'pet_context_id': widget.initialPetId,
    'state': {
      'step': _step,
      'pet': _pet,
      'clinic': _clinic,
      'vet': _vet,
      'slot': _slot,
      'quote': _quote,
      'type': _type,
      'date': _date?.toIso8601String(),
      'request': _request,
      'appointment_id': _appointment?['appointment_id'],
      'history': List<String>.from(_history),
    },
  };

  Future<void> _saveDraft() async {
    if (!_usesDraftStorage) return;

    if (!_draftReady) {
      throw const ApiException(
        'Reload this conversation before continuing the booking.',
      );
    }

    final result = await widget.chatbot!.saveBookingDraft(
      widget.conversationId!,
      expectedRevision: _draftRevision,
      draft: _draftPayload(),
    );

    _draftRevision = result['booking_draft_revision'] as int;
  }

  Future<void> _resumeBooking() async {
    if (!_usesDraftStorage) {
      await _loadStep();
      return;
    }

    setState(() {
      _busy = true;
      _error = null;
      _draftReady = false;
    });

    try {
      final conversation = await widget.chatbot!.getConversation(
        widget.conversationId!,
      );

      if (!mounted) return;

      if (conversation['status'] != 'active' ||
          conversation['pet_id'] != widget.initialPetId) {
        throw const ApiException(
          'This booking no longer matches the active conversation.',
        );
      }

      final revision = conversation['booking_draft_revision'];
      if (revision is! int || revision < 0) {
        throw const ApiException('Invalid booking draft revision.');
      }
      _draftRevision = revision;

      // Clear local state before restoring the server's version.
      _step = 0;
      _pet = null;
      _clinic = null;
      _vet = null;
      _slot = null;
      _quote = null;
      _request = null;
      _appointment = null;
      _date = null;
      _type = null;
      _uncertain = false;
      _history.clear();

      final rawDraft = conversation['booking_draft'];

      if (rawDraft != null) {
        final draft = Map<String, dynamic>.from(rawDraft as Map);

        if (draft['schema_version'] != 1 ||
            draft['conversation_id'] != widget.conversationId ||
            draft['pet_context_id'] != widget.initialPetId) {
          throw const ApiException(
            'Saved booking does not match this conversation.',
          );
        }

        final state = Map<String, dynamic>.from(
          draft['state'] as Map,
        );

        Map<String, dynamic>? readMap(String key) {
          final value = state[key];
          return value == null
              ? null
              : Map<String, dynamic>.from(value as Map);
        }

        final step = state['step'];
        if (step is! int || step < 0 || step > 6) {
          throw const ApiException('Invalid saved booking step.');
        }

        _step = step;
        _pet = readMap('pet');
        _clinic = readMap('clinic');
        _vet = readMap('vet');
        _slot = readMap('slot');
        _quote = readMap('quote');
        _request = readMap('request');
        _type = state['type'] as String?;

        final date = state['date'];
        _date = date == null ? null : DateTime.parse(date as String);

        final history = state['history'];
        if (history is List) {
          _history.addAll(history.whereType<String>().take(7));
        }

        if ((_step >= 1 && _pet == null) ||
            (_step >= 2 && _clinic == null) ||
            (_step >= 3 &&
                !{'dental_checkup', 'consultation'}.contains(_type)) ||
            (_step >= 4 && _vet == null) ||
            (_step >= 5 && _date == null) ||
            (_step >= 6 && _slot == null)) {
          throw const ApiException('Saved booking is incomplete.');
        }

        // Recheck ownership and refresh the selected pet.
        if (_pet != null) {
          final petId = _pet!['pet_id'] as int;

          if (widget.initialPetId != null &&
              petId != widget.initialPetId) {
            throw const ApiException('Saved booking has a different pet.');
          }

          _pet = await widget.pets.getPet(petId);
          if (!mounted) return;
        }

        if (_request != null) {
          if (_step != 6 ||
              _request!['pet_id'] != _pet?['pet_id'] ||
              _request!['time_slot_id'] != _slot?['time_slot_id'] ||
              _request!['appointment_type'] != _type ||
              _request!['booking_request_id'] is! String ||
              _request!['expected_payment_version'] is! int ||
              _request!['expected_deposit_amount'] is! String) {
            throw const ApiException('Invalid saved booking request.');
          }
        }

        final appointmentId = state['appointment_id'];
        if (appointmentId != null) {
          _appointment = await widget.appointments.getAppointmentRecord(
            appointmentId as int,
          );

          if (!mounted) return;

          if (_appointment == null ||
              _appointment!['pet_id'] != _pet?['pet_id']) {
            throw const ApiException(
              'The saved appointment could not be verified.',
            );
          }
        }
      }

      _draftReady = true;

      if (_appointment != null) return;

      if (_request != null) {
        // Never create an appointment automatically during restoration.
        _uncertain = true;
        _error = _resumeWarning;
        return;
      }

      // An unconfirmed old date must be selected again.
      if (_date != null && _date!.isBefore(_today())) {
        _date = null;
        _slot = null;
        _quote = null;
        _step = 4;
        if (_history.length > 4) {
          _history.removeRange(4, _history.length);
        }
      }

      await _loadStep();
    } catch (error) {
      if (!mounted) return;

      _draftReady = false;
      _error = _bookingError(
        error,
        _text(
          'Could not restore the booking. Reload before continuing.',
          'Janji temu tidak dapat dipulihkan. Muat semula sebelum meneruskan.',
          '无法恢复预约，请重新加载后再继续。',
        ),
      );
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _closeBooking() async {
    if (_busy || (_request != null && _appointment == null)) return;

    setState(() => _busy = true);

    try {
      if (_usesDraftStorage) {
        if (!_draftReady) {
          throw const ApiException(
            'Reload this conversation before closing the booking.',
          );
        }

        await widget.chatbot!.saveBookingDraft(
          widget.conversationId!,
          expectedRevision: _draftRevision,
          draft: null,
        );
      }

      if (!mounted) return;
      widget.onCancel();
    } catch (_) {
      if (mounted) await _resumeBooking();
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  String _bookingError(Object error, String fallback) {
    if (error is! ApiException || error.message.trim().isEmpty) {
      return fallback;
    }

    final label = _text(
      'Original server message',
      'Mesej asal pelayan',
      '服务器原始消息',
    );

    return '$fallback\n$label: ${error.message}';
  }

  String _text(String en, String ms, String zh) {
    return switch (widget.language) {
      'ms' => ms,
      'zh' => zh,
      _ => en,
    };
  }

  List<String> get _questions => [
    _text(
      'Which pet is the appointment for?',
      'Janji temu ini untuk haiwan yang mana?',
      '这次预约是为哪只宠物安排的？',
    ),
    _text(
      'Which clinic would you like to visit?',
      'Klinik manakah yang ingin anda kunjungi?',
      '您想选择哪家诊所？',
    ),
    _text(
      'What type of appointment do you need?',
      'Apakah jenis janji temu yang diperlukan?',
      '您需要哪种预约？',
    ),
    _text(
      'Which veterinarian would you prefer?',
      'Doktor veterinar manakah yang anda pilih?',
      '您想选择哪位兽医？',
    ),
    _text(
      'Which date would you like?',
      'Tarikh manakah yang anda pilih?',
      '您想选择哪一天？',
    ),
    _text(
      'Choose an available appointment time.',
      'Pilih waktu janji temu yang tersedia.',
      '请选择可预约的时间。',
    ),
    _text(
      'Please review your appointment before confirming.',
      'Semak butiran janji temu sebelum mengesahkan.',
      '请核对预约信息后再确认。',
    ),
  ];

  String _bookingLabel(String english) {
    const translations = <String, List<String>>{
      'Choose date': ['Pilih tarikh', '选择日期'],
      'Confirm booking': ['Sahkan janji temu', '确认预约'],
      'Back': ['Kembali', '返回'],
      'Open booking page instead': [
        'Buka halaman janji temu',
        '打开预约页面',
      ],
      'Retry same booking': [
        'Cuba semula janji temu yang sama',
        '重试同一预约',
      ],
      'Reload choices': ['Muat semula pilihan', '重新加载选项'],
      'Pay deposit / check payment status': [
        'Bayar deposit / semak status pembayaran',
        '支付订金／查看付款状态',
      ],
      'Dental checkup': ['Pemeriksaan pergigian', '牙齿检查'],
      'Consultation': ['Konsultasi', '诊疗咨询'],
    };

    final values = translations[english];
    if (values == null) return english;

    return _text(english, values[0], values[1]);
  }

  String _appointmentStatus(Map<String, dynamic> appointment) {
    final id = appointment['appointment_id'];
    final status = appointment['status'];

    return switch (status) {
      'confirmed' => _text(
        'Appointment #$id confirmed.',
        'Janji temu #$id telah disahkan.',
        '预约 #$id 已确认。',
      ),
      'pending_payment' => _text(
        'Appointment #$id is awaiting payment.',
        'Janji temu #$id sedang menunggu pembayaran.',
        '预约 #$id 正在等待付款。',
      ),
      'cancelled' => _text(
        'Appointment #$id was cancelled.',
        'Janji temu #$id telah dibatalkan.',
        '预约 #$id 已取消。',
      ),
      'completed' => _text(
        'Appointment #$id is completed.',
        'Janji temu #$id telah selesai.',
        '预约 #$id 已完成。',
      ),
      _ => _text(
        'Appointment #$id — recorded status: $status',
        'Janji temu #$id — status direkodkan: $status',
        '预约 #$id — 已记录状态：$status',
      ),
    };
  }

  @override
  void initState() {
    super.initState();
    _resumeBooking();
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

          final selectedPetId = widget.initialPetId;

          if (selectedPetId != null) {
            Map<String, dynamic>? selectedPet;

            for (final pet in choices) {
              if (pet['pet_id'] == selectedPetId) {
                selectedPet = pet;
                break;
              }
            }

            if (selectedPet == null) {
              throw ApiException(
                _text(
                  'The pet linked to this chat is unavailable. Start a new chat.',
                  'Haiwan yang dipautkan kepada perbualan ini tidak tersedia. Mulakan perbualan baharu.',
                  '此对话关联的宠物不可用，请开始新对话。',
                ),
              );
            }

            setState(() {
              _pet = selectedPet;
              _history.add(
                '${_questions[0]}\n${selectedPet!['pet_name']}',
              );
              _step = 1;
            });

            await _loadStep();
            return;
          }
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
      await _saveDraft();
      if (!mounted) return;
      setState(() => _choices = choices);
    } catch (error) {
      if (mounted) {
        setState(() {
          _error = _bookingError(
            error,
            _text(
              'Could not load booking choices. Please try again.',
              'Pilihan janji temu tidak dapat dimuatkan. Cuba lagi.',
              '无法加载预约选项，请重试。',
            ),
          );
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
        return _bookingLabel('${item['label']}');
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
      locale: switch (widget.language) {
        'ms' => const Locale('ms'),
        'zh' => const Locale('zh', 'CN'),
        _ => const Locale('en'),
      },
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
    if (_busy ||
        (_quote == null && _request == null) ||
        _appointment != null) {
      return;
    }

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

    // A booking cannot be submitted until its request ID is saved.
    try {
      await _saveDraft();
    } catch (_) {
      if (mounted) await _resumeBooking();
      return;
    }

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

      try {
        await _saveDraft();
      } catch (_) {
        // The frozen request was saved before submission.
        // Reopening can safely retry that same request ID.
      }
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
            ? _text(
          'The booking response could not be confirmed. '
              'Tap Retry same booking before making another booking.',
          'Respons janji temu belum dapat disahkan. '
              'Tekan Cuba semula janji temu yang sama sebelum membuat janji temu lain.',
          '暂时无法确认预约是否已成功。'
              '请先点击“重试同一预约”，再考虑创建其他预约。',
        )
            : _bookingError(
          error,
          _text(
            'The booking could not be created.',
            'Janji temu tidak dapat dibuat.',
            '无法创建预约。',
          ),
        );
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
              Expanded(
                child: Text(
                  _text(
                    'Appointment assistant',
                    'Pembantu janji temu',
                    '预约助手',
                  ),
                  style: const TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
              IconButton(
                tooltip: appointment != null
                    ? _text(
                  'Close booking summary',
                  'Tutup ringkasan janji temu',
                  '关闭预约摘要',
                )
                    : _text(
                  'Cancel booking steps',
                  'Batalkan langkah janji temu',
                  '取消预约步骤',
                ),
                onPressed: _busy || (_request != null && appointment == null)
                    ? null
                    : _closeBooking,
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
              _appointmentStatus(appointment),
              style: const TextStyle(fontWeight: FontWeight.w700),
            ),
            if (appointment['status'] == 'pending_payment') ...[
              const SizedBox(height: 8),
              Text(
                _text(
                  'Complete the deposit payment to confirm your appointment. '
                      'If you already paid, open payment status to check it.',
                  'Lengkapkan pembayaran deposit untuk mengesahkan janji temu. '
                      'Jika sudah membayar, buka status pembayaran untuk menyemaknya.',
                  '请完成订金支付以确认预约。'
                      '如果已经付款，请打开付款状态进行检查。',
                ),
              ),
              const SizedBox(height: 12),
              FilledButton(
                onPressed: _busy ? null : _openPayment,
                child: Text(_bookingLabel('Pay deposit / check payment status'))
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
                  label: Text(_bookingLabel('Choose date')),
                )
              else if (_step == 6 && _quote != null) ...[
                Text(
                  '${_text('Deposit', 'Deposit', '订金')}: RM '
                      '${num.parse('${_quote!['deposit_amount']}').toStringAsFixed(2)}',
                  style: const TextStyle(fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 8),
                Text(
                  _text(
                    'All appointment times use Malaysia time. '
                        'Any deposit is deducted from the final consultation bill.',
                    'Semua waktu janji temu menggunakan waktu Malaysia. '
                        'Deposit ditolak daripada bil konsultasi akhir.',
                    '所有预约时间均为马来西亚时间。'
                        '已支付的订金将从最终诊疗账单中扣除。',
                  ),
                ),
                const SizedBox(height: 12),
                FilledButton(
                  onPressed: _confirm,
                  child:
                  Text(_bookingLabel('Confirm booking')),
                ),
              ] else if (_choices.isEmpty)
              Text(
              _step == 5
              ? _text(
              'No slots are available. Go back and choose another date.',
              'Tiada slot tersedia. Kembali dan pilih tarikh lain.',
              '没有可预约的时段。请返回并选择其他日期。',
              )
                  : _text(
              'No choices are available. Go back or use the booking page.',
              'Tiada pilihan tersedia. Kembali atau buka halaman janji temu.',
              '没有可用选项。请返回或打开预约页面。',
              ),
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
                    : () => _resumeBooking(),
                child: Text(
                  _bookingLabel(
                    _uncertain
                        ? 'Retry same booking'
                        : 'Reload choices',
                  ),
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
                    child: Text(_bookingLabel('Back')),
                  ),
                TextButton(
                  onPressed: _busy || _request != null
                      ? null
                      : widget.onOpenBookingPage,
                  child: Text(_bookingLabel('Open booking page instead')),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}