import 'package:flutter/material.dart';

import '../services/api_client.dart';
import '../services/appointment_service.dart';
import '../services/followup_service.dart';
import 'followup_updates.dart';

class AppointmentDetailsScreen extends StatefulWidget {
  final Map<String, dynamic> appointment;
  final AppointmentService service;

  const AppointmentDetailsScreen({
    super.key,
    required this.appointment,
    required this.service,
  });

  @override
  State<AppointmentDetailsScreen> createState() =>
      _AppointmentDetailsScreenState();
}

class _AppointmentDetailsScreenState
    extends State<AppointmentDetailsScreen> {
  late Future<Map<String, dynamic>?> _record;

  @override
  void initState() {
    super.initState();
    _record = _fetch();
  }

  Future<Map<String, dynamic>?> _fetch() {
    return widget.service.getAppointmentRecord(
      widget.appointment['appointment_id'] as int,
    );
  }

  Future<void> _refresh() async {
    setState(() => _record = _fetch());

    try {
      await _record;
    } catch (_) {
      // FutureBuilder displays the error.
    }
  }

  String _text(dynamic value) {
    final text = value?.toString().trim();
    return text == null || text.isEmpty ? 'Not recorded' : text;
  }

  String _date(dynamic value) {
    final parsed = DateTime.tryParse(value?.toString() ?? '');
    if (parsed == null) return _text(value);

    return '${parsed.day.toString().padLeft(2, '0')}/'
        '${parsed.month.toString().padLeft(2, '0')}/'
        '${parsed.year}';
  }

  String _time(dynamic value) {
    final text = _text(value);
    return text.length >= 5 ? text.substring(0, 5) : text;
  }

  Widget _field(String label, dynamic value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Text('$label: ${_text(value)}'),
    );
  }

  Widget _section(String title, List<Widget> children) {
    return Card(
      margin: const EdgeInsets.only(bottom: 16),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              title,
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 12),
            ...children,
          ],
        ),
      ),
    );
  }

  Future<void> _openFollowup(Map<String, dynamic> followup) async {
    await Navigator.of(context).push<void>(
      MaterialPageRoute(
        builder: (_) => FollowupUpdatesScreen(
          followup: followup,
          service: FollowupService(widget.service.api),
        ),
      ),
    );

    if (mounted) await _refresh();
  }

  List<Widget> _medicalSections(Map<String, dynamic> record) {
    final treatments = record['treatments'] as List;
    final prescriptions = record['prescriptions'] as List;
    final followups = record['followups'] as List;

    return [
      _section('Consultation Summary', [
        _field('Consultation', '#${record['consultation_id']}'),
        _field('Diagnosis', record['diagnosis']),
      ]),
      _section('Treatments', [
        if (treatments.isEmpty)
          const Text('No treatments recorded.'),
        for (final treatment in treatments)
          Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _field('Treatment', treatment['treatment_name']),
                _field(
                  'Status',
                  _text(treatment['current_status'])
                      .replaceAll('_', ' '),
                ),
                _field('Date', _date(treatment['treatment_date'])),
                _field('Description', treatment['description']),
              ],
            ),
          ),
      ]),
      _section('Prescriptions', [
        if (prescriptions.isEmpty)
          const Text('No prescriptions recorded.'),
        for (final prescription in prescriptions)
          Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _field('Medication', prescription['medication_name']),
                _field('Dosage', prescription['dosage']),
                _field('Route', prescription['administration_route']),
                _field('Frequency', prescription['frequency']),
                _field('Duration', prescription['duration']),
                _field('Instructions', prescription['instructions']),
              ],
            ),
          ),
      ]),
      _section('Follow-up Care', [
        if (followups.isEmpty)
          const Text('No follow-up care requested for this visit.'),
        for (final item in followups)
          _followupCard(Map<String, dynamic>.from(item as Map)),
      ]),
    ];
  }

  Widget _followupCard(Map<String, dynamic> followup) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _field(
            'Status',
            _text(followup['status']).replaceAll('_', ' '),
          ),
          _field('Review date', _date(followup['recommended_date'])),
          _field('Reason', followup['reason']),
          _field('Home-care instructions', followup['care_instructions']),
          _field(
            'Photos required',
            followup['photos_required'] == true ? 'Yes' : 'No',
          ),
          if (followup['photos_required'] == true)
            _field('Photo instructions', followup['photo_instructions']),
          _field(
            'In-clinic review required',
            followup['visit_required'] == true ? 'Yes' : 'No',
          ),
          const SizedBox(height: 8),
          OutlinedButton.icon(
            onPressed: () => _openFollowup(followup),
            icon: const Icon(Icons.photo_camera_outlined),
            label: Text(
              followup['status'] == 'pending'
                  ? 'Send Photos / Update'
                  : 'View Updates & Feedback',
            ),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final appointment = widget.appointment;

    return Scaffold(
      appBar: AppBar(title: const Text('Appointment Details')),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.all(16),
          children: [
            _section('Appointment', [
              _field('Pet', appointment['pet_name']),
              _field('Clinic', appointment['clinic_name']),
              _field('Address', appointment['clinic_address']),
              _field('Veterinarian', appointment['veterinarian_name']),
              _field('Date', _date(appointment['appointment_date'])),
              _field(
                'Time',
                '${_time(appointment['start_time'])}–'
                    '${_time(appointment['end_time'])} MYT',
              ),
              _field(
                'Type',
                _text(appointment['appointment_type'])
                    .replaceAll('_', ' '),
              ),
              _field(
                'Status',
                appointment['needs_rearrangement'] == true
                    ? 'Needs rearrangement — contact the clinic'
                    : _text(appointment['status']).replaceAll('_', ' '),
              ),
            ]),
            FutureBuilder<Map<String, dynamic>?>(
              future: _record,
              builder: (context, snapshot) {
                if (snapshot.connectionState != ConnectionState.done) {
                  return const Padding(
                    padding: EdgeInsets.all(24),
                    child: Center(child: CircularProgressIndicator()),
                  );
                }

                if (snapshot.hasError) {
                  final error = snapshot.error;

                  return _section('Medical Record', [
                    Text(
                      error is ApiException
                          ? error.message
                          : 'Could not load the medical record.',
                    ),
                    TextButton(
                      onPressed: _refresh,
                      child: const Text('Retry'),
                    ),
                  ]);
                }

                final record = snapshot.data;

                if (record == null) {
                  return _section('Medical Record', [
                    const Text(
                      'No completed consultation record is available '
                          'for this appointment.',
                    ),
                  ]);
                }

                return Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: _medicalSections(record),
                );
              },
            ),
          ],
        ),
      ),
    );
  }
}