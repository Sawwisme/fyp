import 'package:flutter/material.dart';

import '../services/api_client.dart';
import '../services/pet_service.dart';

class MedicalHistoryScreen extends StatefulWidget {
  final int petId;
  final String petName;
  final PetService service;

  const MedicalHistoryScreen({
    super.key,
    required this.petId,
    required this.petName,
    required this.service,
  });

  @override
  State<MedicalHistoryScreen> createState() =>
      _MedicalHistoryScreenState();
}

class _MedicalHistoryScreenState extends State<MedicalHistoryScreen> {
  static const _pageSize = 10;

  late Future<List<Map<String, dynamic>>> _future;
  int _page = 0;

  @override
  void initState() {
    super.initState();
    _future = _fetch(0);
  }

  Future<List<Map<String, dynamic>>> _fetch(int page) {
    return widget.service.getMedicalHistory(
      widget.petId,
      offset: page * _pageSize,
      limit: _pageSize + 1,
    );
  }

  void _load(int page) {
    setState(() {
      _page = page;
      _future = _fetch(page);
    });
  }

  Future<void> _refresh() async {
    _load(0);

    try {
      await _future;
    } catch (_) {
      // FutureBuilder displays the request error.
    }
  }

  String _text(dynamic value) {
    final text = value?.toString().trim();
    return text == null || text.isEmpty ? 'Not recorded' : text;
  }

  String _status(dynamic value) {
    return _text(value).replaceAll('_', ' ');
  }

  String _date(dynamic value) {
    if (value == null) return 'Not recorded';

    final parts = value.toString().split('-');
    if (parts.length != 3) return _text(value);

    return '${parts[2]}/${parts[1]}/${parts[0]}';
  }

  String _visitDate(dynamic value) {
    if (value == null) return 'Not recorded';

    var text = value.toString();
    final hasZone = RegExp(
      r'(Z|[+-]\d{2}:\d{2})$',
      caseSensitive: false,
    ).hasMatch(text);

    if (!hasZone) text = '${text}Z';

    final parsed = DateTime.tryParse(text);
    if (parsed == null) return 'Not recorded';

    final malaysia = parsed.toUtc().add(const Duration(hours: 8));
    String two(int number) => number.toString().padLeft(2, '0');

    return '${two(malaysia.day)}/${two(malaysia.month)}/'
        '${malaysia.year} · ${two(malaysia.hour)}:'
        '${two(malaysia.minute)} MYT';
  }

  Widget _field(String label, dynamic value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Text('$label: ${_text(value)}'),
    );
  }

  Widget _section(String title, List<Widget> children) {
    return Padding(
      padding: const EdgeInsets.only(top: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          if (children.isEmpty)
            const Text('None recorded.')
          else
            ...children,
        ],
      ),
    );
  }

  Widget _record(Map<String, dynamic> record) {
    final treatments = record['treatments'] as List;
    final prescriptions = record['prescriptions'] as List;
    final followups = record['followups'] as List;

    return Card(
      child: ExpansionTile(
        key: ValueKey(record['consultation_id']),
        title: Text(_text(record['clinic_name'])),
        subtitle: Text(
          '${_visitDate(record['consultation_date'])}\n'
              '${_text(record['veterinarian_name'])}',
        ),
        childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
        expandedCrossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _field('Consultation', '#${record['consultation_id']}'),
          _field('Diagnosis', record['diagnosis']),
          _section('Treatments', [
            for (final treatment in treatments)
              Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _field('Treatment', treatment['treatment_name']),
                    _field('Date', _date(treatment['treatment_date'])),
                    _field(
                      'Current status',
                      _status(treatment['current_status']),
                    ),
                    _field('Description', treatment['description']),
                  ],
                ),
              ),
          ]),
          _section('Prescriptions', [
            for (final prescription in prescriptions)
              Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _field('Medication', prescription['medication_name']),
                    _field(
                      'Prescribed',
                      _date(prescription['prescription_date']),
                    ),
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
            for (final followup in followups)
              Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _field(
                      'Recommended review',
                      _date(followup['recommended_date']),
                    ),
                    _field('Status', _status(followup['status'])),
                    _field('Reason', followup['reason']),
                    _field(
                      'Home-care instructions',
                      followup['care_instructions'],
                    ),
                    if (followup['followup_date'] != null)
                      _field(
                        'Reviewed',
                        _visitDate(followup['followup_date']),
                      ),
                  ],
                ),
              ),
          ]),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('${widget.petName} — Medical History')),
      body: FutureBuilder<List<Map<String, dynamic>>>(
        future: _future,
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }

          if (snapshot.hasError) {
            final error = snapshot.error;

            return ListView(
              padding: const EdgeInsets.all(24),
              children: [
                Text(
                  error is ApiException
                      ? error.message
                      : 'Unable to load medical history.',
                ),
                const SizedBox(height: 16),
                FilledButton(
                  onPressed: () => _load(_page),
                  child: const Text('Retry'),
                ),
              ],
            );
          }

          final data = snapshot.data!;
          final visible = data.take(_pageSize).toList();

          return RefreshIndicator(
            onRefresh: _refresh,
            child: ListView(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.all(16),
              children: [
                const Text(
                  'Completed consultation records from your pet’s clinics.',
                ),
                const SizedBox(height: 12),
                if (visible.isEmpty)
                  const Padding(
                    padding: EdgeInsets.symmetric(vertical: 32),
                    child: Text('No completed medical records yet.'),
                  ),
                for (final record in visible) _record(record),
                const SizedBox(height: 16),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    OutlinedButton(
                      onPressed: _page > 0
                          ? () => _load(_page - 1)
                          : null,
                      child: const Text('Previous'),
                    ),
                    Text('Page ${_page + 1}'),
                    OutlinedButton(
                      onPressed: data.length > _pageSize
                          ? () => _load(_page + 1)
                          : null,
                      child: const Text('Next'),
                    ),
                  ],
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}