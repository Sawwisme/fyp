import 'package:flutter/material.dart';

import '../services/ai_assessment_review_service.dart';
import '../services/api_client.dart';
import '../services/appointment_service.dart';

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
  List<Map<String, dynamic>> _reviews = [];
  Map<String, dynamic>? _selected;
  bool _loading = true;
  bool _reading = false;
  bool _hasNext = false;
  bool _booking = false;
  int _page = 0;
  String? _error;

  bool get _busy => _loading || _reading || _booking;

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
      appBar: AppBar(title: const Text('Vet feedback')),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.all(20),
          children: [
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
              'Assessment feedback',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 12),
            if (!_loading && _reviews.isEmpty && _error == null)
              const Text('No assessment feedback recorded.'),
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
