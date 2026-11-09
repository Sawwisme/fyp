import 'package:flutter/material.dart';

import '../services/ai_assessment_review_service.dart';
import '../services/api_client.dart';
import '../services/appointment_service.dart';
import 'clinic_picker.dart';

import 'book_appointment.dart';
import '../services/pet_service.dart';

class AIAssessmentReviewsScreen extends StatefulWidget {
  final AIAssessmentReviewService service;
  final int? analysisId;
  final int? reviewId;

  const AIAssessmentReviewsScreen({
    super.key,
    required this.service,
    this.analysisId,
    this.reviewId,
  });

  @override
  State<AIAssessmentReviewsScreen> createState() =>
      _AIAssessmentReviewsScreenState();
}

class _AIAssessmentReviewsScreenState extends State<AIAssessmentReviewsScreen>
    with WidgetsBindingObserver {
  static const _blue = Color(0xFF2549C7);
  static const _size = 20;
  final _message = TextEditingController();
  final _form = GlobalKey<FormState>();
  List<Map<String, dynamic>> _reviews = [];
  Map<String, dynamic>? _clinic;
  Map<String, dynamic>? _selected;
  bool _loading = true, _sending = false, _reading = false, _choosing = false;
  bool _hasNext = false, _uncertain = false;
  bool _booking = false;
  int _page = 0;
  String? _error, _notice;

  bool get _busy =>
      _loading || _sending || _reading || _choosing || _booking;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _load(0).then((_) {
      final id = widget.reviewId;
      if (mounted && id != null && _error == null) {
        _read(id);
      }
    });
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _message.dispose();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed && !_busy) _refresh();
  }

  String _errorText(Object error) => error is ApiException
      ? error.message
      : 'Unable to reach the server. Please try again.';

  Future<void> _load(int page) async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final records = await widget.service.list(
        offset: page * _size,
        limit: _size + 1,
      );
      if (!mounted) return;
      setState(() {
        _reviews = records.take(_size).toList();
        _hasNext = records.length > _size;
        _page = page;
      });
    } catch (error) {
      if (mounted) setState(() => _error = _errorText(error));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _read(int id) async {
    if (_busy) return;
    setState(() {
      _reading = true;
      _error = null;
      _selected = null;
    });
    try {
      final record = await widget.service.get(id);
      if (mounted) setState(() => _selected = record);
    } catch (error) {
      if (mounted) setState(() => _error = _errorText(error));
    } finally {
      if (mounted) setState(() => _reading = false);
    }
  }

  Future<void> _refresh() async {
    if (_busy) return;
    final id = _selected?['review_id'] as int?;
    await _load(_page);
    if (mounted && id != null && _error == null) await _read(id);
  }

  Future<void> _chooseClinic() async {
    if (_busy || _uncertain) return;
    setState(() => _choosing = true);
    try {
      final clinic = await Navigator.of(context).push<Map<String, dynamic>>(
        MaterialPageRoute(
          builder: (_) => ClinicPickerScreen(
            service: AppointmentService(widget.service.api),
          ),
        ),
      );
      if (mounted && clinic != null) {
        setState(() {
          _clinic = clinic;
          _notice = null;
          _error = null;
        });
      }
    } finally {
      if (mounted) setState(() => _choosing = false);
    }
  }

  Future<void> _send() async {
    if (_busy || _clinic == null || widget.analysisId == null) return;
    if (!(_form.currentState?.validate() ?? false)) return;
    final analysisId = widget.analysisId!;
    final clinicId = _clinic!['clinic_id'] as int;
    final wasUncertain = _uncertain;
    setState(() {
      _sending = true;
      _error = null;
      _notice = null;
    });
    try {
      final record = await widget.service.request(
        analysisId: analysisId,
        clinicId: clinicId,
        ownerMessage: _message.text,
      );
      if (!mounted) return;
      setState(() {
        _selected = record;
        _uncertain = false;
        _notice = record['status'] == 'reviewed'
            ? 'This clinic has already reviewed the assessment. View its feedback below.'
            : 'Your request is awaiting a vet review. This does not book an appointment.';
      });
    } on ApiException catch (error) {
      if (!mounted) return;
      setState(() {
        _uncertain =
            wasUncertain ||
                error.statusCode == null ||
                (error.statusCode ?? 0) >= 500;
        _error = _uncertain
            ? 'The request could not be confirmed. Keep this clinic selected and retry the same request; the server prevents duplicate requests.'
            : error.message;
      });
    } catch (_) {
      if (mounted)
        setState(() {
          _uncertain = true;
          _error =
          'The request could not be confirmed. Retry the same clinic and assessment to check it.';
        });
    } finally {
      if (mounted) setState(() => _sending = false);
    }
    if (mounted && _error == null) await _load(0);
  }

  String _label(Object? value) => switch (value) {
    'pending' => 'Awaiting vet review',
    'reviewed' => 'Reviewed by veterinarian',
    'cancelled' => 'Cancelled',
    'routine_booking' => 'Routine appointment recommended',
    'prompt_clinic_assessment' => 'Prompt clinic assessment recommended',
    'home_care' => 'Follow the vet’s home-care guidance',
    'unable_to_assess' => 'Unable to assess from this image',
    'none' => 'No concern identified from this image',
    'mild' => 'Mild',
    'moderate' => 'Moderate',
    'severe' => 'Severe',
    _ => value?.toString() ?? 'Not recorded',
  };

  String _date(Object? value) {
    final parsed = DateTime.tryParse(value?.toString() ?? '');
    if (parsed == null) return 'Not recorded';
    final date = parsed.toUtc().add(const Duration(hours: 8));
    String two(int n) => n.toString().padLeft(2, '0');
    return '${two(date.day)}/${two(date.month)}/${date.year} · ${two(date.hour)}:${two(date.minute)} MYT';
  }

  Widget _card(List<Widget> children) => Card(
    color: Colors.white,
    margin: const EdgeInsets.only(bottom: 16),
    child: Padding(
      padding: const EdgeInsets.all(18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: children,
      ),
    ),
  );

  Future<void> _bookReviewedAssessment() async {
    if (_busy || _selected == null) return;

    final reviewId = _selected!['review_id'] as int;
    var openedBooking = false;

    setState(() {
      _booking = true;
      _error = null;
    });

    try {
      // Read the saved recommendation again before opening booking.
      final record = await widget.service.get(reviewId);

      if (!mounted) return;

      setState(() => _selected = record);

      if (record['status'] != 'reviewed' ||
          !{
            'routine_booking',
            'prompt_clinic_assessment',
          }.contains(record['recommended_action'])) {
        throw const ApiException(
          'This review does not currently recommend booking a clinic '
              'appointment. Read the latest feedback.',
        );
      }

      final appointmentService = AppointmentService(
        widget.service.api,
      );

      Map<String, dynamic>? clinic;

      for (var offset = 0; ; offset += 100) {
        final batch = await appointmentService.getClinics(
          offset: offset,
          limit: 100,
        );

        if (!mounted) return;

        for (final item in batch) {
          if (item['clinic_id'] == record['clinic_id']) {
            clinic = item;
            break;
          }
        }

        if (clinic != null || batch.length < 100) break;
      }

      if (clinic == null) {
        throw const ApiException(
          'The reviewing clinic is not currently available for online '
              'booking. Contact the clinic directly.',
        );
      }

      if (!mounted) return;

      openedBooking = true;

      await Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => BookAppointmentScreen(
            clinic: clinic!,
            service: appointmentService,
            petService: PetService(widget.service.api),
            initialPetId: record['pet_id'] as int,
            aiAssessmentReviewId: record['review_id'] as int,
          ),
        ),
      );
    } catch (error) {
      if (mounted) {
        setState(() => _error = _errorText(error));
      }
    } finally {
      if (mounted) {
        setState(() => _booking = false);
      }
    }

    if (mounted && openedBooking && _error == null) {
      await _refresh();
    }
  }

  Widget _feedback() {
    final record = _selected!;
    final reviewed = record['status'] == 'reviewed';
    return _card([
      Text(
        '${record['pet_name']} · ${record['clinic_name']}',
        style: Theme.of(context).textTheme.titleMedium,
      ),
      const SizedBox(height: 8),
      Text(
        _label(record['status']),
        style: const TextStyle(color: _blue, fontWeight: FontWeight.bold),
      ),
      if (reviewed) ...[
        const SizedBox(height: 16),
        Text('Vet interpretation: ${_label(record['reviewed_severity'])}'),
        const SizedBox(height: 8),
        Text(
          _label(record['recommended_action']),
          style: const TextStyle(fontWeight: FontWeight.w600),
        ),
        const SizedBox(height: 12),
        SelectableText(record['feedback']?.toString() ?? ''),
        const SizedBox(height: 12),
        Text(
          '${record['reviewed_by_name'] ?? 'Veterinarian'} · ${_date(record['reviewed_at'])}',
          style: Theme.of(context).textTheme.bodySmall,
        ),
      ] else ...[
        const SizedBox(height: 12),
        const Text(
          'Your selected clinic can view the shared photo and AI results. Pull down to check for feedback. A review request does not reserve an appointment.',
        ),
      ],
      if (reviewed &&
          {
            'routine_booking',
            'prompt_clinic_assessment',
          }.contains(record['recommended_action'])) ...[
        const SizedBox(height: 16),
        FilledButton.icon(
          onPressed: _busy ? null : _bookReviewedAssessment,
          icon: const Icon(Icons.calendar_month_outlined),
          label: Text(
            _booking
                ? 'Opening booking…'
                : 'Choose appointment time',
          ),
        ),
        const SizedBox(height: 8),
        const Text(
          'Choose an available vet, date and time at the reviewing '
              'clinic. Your booking is submitted only after you confirm it.',
          style: TextStyle(fontSize: 12),
        ),
      ],
      if (record['ai_severity'] is Map) ...[
        const Divider(height: 28),
        Text(
          'Original AI reference: ${(record['ai_severity'] as Map)['label'] ?? 'Not recorded'}',
        ),
        const Text(
          'The original AI result is preserved separately from the vet’s interpretation.',
          style: TextStyle(fontSize: 12),
        ),
      ],
    ]);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Vet assessment reviews')),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.all(20),
          children: [
            if (widget.analysisId != null)
              _card([
                Text(
                  'Request a vet review',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                const SizedBox(height: 8),
                Text('Assessment #${widget.analysisId}'),
                const SizedBox(height: 8),
                const Text(
                  'Choose a clinic. Sending shares this assessment’s photo and AI results with its authorised veterinarians. It does not book an appointment.',
                ),
                const SizedBox(height: 14),
                OutlinedButton.icon(
                  onPressed: _busy || _uncertain ? null : _chooseClinic,
                  icon: const Icon(Icons.local_hospital_outlined),
                  label: Text(
                    _clinic?['clinic_name']?.toString() ?? 'Select clinic',
                  ),
                ),
                const SizedBox(height: 12),
                Form(
                  key: _form,
                  child: TextFormField(
                    controller: _message,
                    maxLines: 3,
                    maxLength: 2000,
                    enabled: !_sending && !_uncertain,
                    decoration: const InputDecoration(
                      labelText: 'Message for the vet (optional)',
                      border: OutlineInputBorder(),
                    ),
                  ),
                ),
                const SizedBox(height: 10),
                FilledButton.icon(
                  onPressed: _busy || _clinic == null ? null : _send,
                  icon: const Icon(Icons.send_outlined),
                  label: Text(
                    _sending
                        ? 'Sending…'
                        : _uncertain
                        ? 'Retry same request'
                        : 'Share assessment & request review',
                  ),
                ),
              ]),
            if (_notice != null)
              Padding(
                padding: const EdgeInsets.only(bottom: 16),
                child: Text(_notice!),
              ),
            if (_error != null)
              _card([
                Text(
                  _error!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
                TextButton(
                  onPressed: _busy ? null : _refresh,
                  child: const Text('Refresh reviews'),
                ),
              ]),
            if (_reading || _loading)
              const Padding(
                padding: EdgeInsets.all(16),
                child: Center(child: CircularProgressIndicator()),
              ),
            if (_selected != null) _feedback(),
            Text(
              'Your review requests',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 12),
            if (!_loading && _reviews.isEmpty && _error == null)
              const Text('No review requests yet.'),
            for (final record in _reviews)
              Card(
                color: Colors.white,
                child: ListTile(
                  isThreeLine: true,
                  title: Text(
                    '${record['pet_name']} · ${record['clinic_name']}',
                  ),
                  subtitle: Text(
                    '${_label(record['status'])}\nAssessment #${record['analysis_id']} · ${_date(record['requested_at'])}',
                  ),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: _busy ? null : () => _read(record['review_id'] as int),
                ),
              ),
            const SizedBox(height: 12),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                OutlinedButton(
                  onPressed: _busy || _page == 0
                      ? null
                      : () => _load(_page - 1),
                  child: const Text('Previous'),
                ),
                Text('Page ${_page + 1}'),
                OutlinedButton(
                  onPressed: _busy || !_hasNext ? null : () => _load(_page + 1),
                  child: const Text('Next'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
