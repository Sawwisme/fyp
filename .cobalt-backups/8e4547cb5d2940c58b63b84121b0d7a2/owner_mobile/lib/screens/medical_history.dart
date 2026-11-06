import 'package:flutter/material.dart';

import '../services/api_client.dart';
import '../services/pet_service.dart';

import '../services/followup_service.dart';
import 'followup_updates.dart';

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

  late int _selectedPetId;
  late String _selectedPetName;
  late Future<List<Map<String, dynamic>>> _pets;

  Future<List<Map<String, dynamic>>> _fetchPets() async {
    final pets = <Map<String, dynamic>>[];
    var offset = 0;

    while (true) {
      final page = await widget.service.getPets(
        offset: offset,
        limit: 100,
      );

      pets.addAll(page);

      if (page.length < 100) break;
      offset += page.length;
    }

    return pets;
  }

  @override
  void initState() {
    super.initState();

    _selectedPetId = widget.petId;
    _selectedPetName = widget.petName;
    _pets = _fetchPets();
    _future = _fetch(0);
  }

  Future<List<Map<String, dynamic>>> _fetch(int page) {
    return widget.service.getMedicalHistory(
      _selectedPetId,
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
          Text(title, style: Theme
              .of(context)
              .textTheme
              .titleMedium),
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
      key: ValueKey('$_selectedPetId-${record['consultation_id']}'),
      color: Colors.white,
      surfaceTintColor: Colors.transparent,
      elevation: 0,
      margin: const EdgeInsets.only(bottom: 12),
      clipBehavior: Clip.antiAlias,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: const BorderSide(color: Color(0xFFDCE6DE)),
      ),
      child: ExpansionTile(
        key: ValueKey(record['consultation_id']),
        tilePadding: const EdgeInsets.all(16),
        childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
        expandedCrossAxisAlignment: CrossAxisAlignment.start,
        iconColor: const Color(0xFF176B32),
        collapsedIconColor: const Color(0xFF6B786E),
        shape: const Border(),
        collapsedShape: const Border(),
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              _visitDate(record['consultation_date']),
              style: const TextStyle(
                fontSize: 15,
                fontWeight: FontWeight.w700,
                color: Color(0xFF24372A),
              ),
            ),
            const SizedBox(height: 8),
            Container(
              padding: const EdgeInsets.symmetric(
                horizontal: 9,
                vertical: 4,
              ),
              decoration: BoxDecoration(
                color: const Color(0xFFE8F3EB),
                borderRadius: BorderRadius.circular(20),
              ),
              child: const Text(
                'Completed',
                style: TextStyle(
                  color: Color(0xFF176B32),
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ],
        ),
        subtitle: Padding(
          padding: const EdgeInsets.only(top: 10),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                _text(record['clinic_name']),
                style: const TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w500,
                  color: Color(0xFF34483A),
                ),
              ),
              const SizedBox(height: 4),
              Text(
                'Veterinarian: ${_text(record['veterinarian_name'])}',
                style: const TextStyle(
                  fontSize: 12,
                  color: Color(0xFF6B786E),
                ),
              ),
            ],
          ),
        ),
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
                      'Photo submission required',
                      followup['photos_required'] == true ? 'Yes' : 'No',
                    ),
                    if (followup['photos_required'] == true)
                      _field(
                          'Photo requirements', followup['photo_instructions']),
                    _field(
                      'In-clinic review required',
                      followup['visit_required'] == true ? 'Yes' : 'No',
                    ),
                    _field(
                      'Home-care instructions',
                      followup['care_instructions'],
                    ),
                    if (followup['followup_date'] != null)
                      _field(
                        'Reviewed',
                        _visitDate(followup['followup_date']),
                      ),

                    const SizedBox(height: 8),

                    OutlinedButton.icon(
                      onPressed: () {
                        Navigator.of(context).push(
                          MaterialPageRoute(
                            builder: (_) =>
                                FollowupUpdatesScreen(
                                  followup: Map<String, dynamic>.from(
                                      followup as Map),
                                  service: FollowupService(widget.service.api),
                                ),
                          ),
                        );
                      },
                      icon: const Icon(Icons.photo_camera_outlined),
                      label: Text(
                        followup['status'] == 'pending'
                            ? 'Send Photos / Update'
                            : 'View Updates & Feedback',
                      ),
                    ),
                  ],
                ),
              ),
          ]),
        ],
      ),
    );
  }

  Widget _petSelector() {
    return FutureBuilder<List<Map<String, dynamic>>>(
      future: _pets,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const LinearProgressIndicator();
        }

        if (snapshot.hasError) {
          return Row(
            children: [
              const Expanded(
                child: Text('Could not load your pets.'),
              ),
              TextButton(
                onPressed: () {
                  setState(() => _pets = _fetchPets());
                },
                child: const Text('Retry'),
              ),
            ],
          );
        }

        final pets = snapshot.data ?? [];

        if (pets.isEmpty) {
          return const Text('No pets available.');
        }

        return Material(
          color: Colors.white,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(14),
            side: const BorderSide(color: Color(0xFFDCE6DE)),
          ),
          clipBehavior: Clip.antiAlias,
          child: InkWell(
            onTap: () async {
              final selected =
              await showModalBottomSheet<Map<String, dynamic>>(
                context: context,
                showDragHandle: true,
                backgroundColor: Colors.white,
                builder: (sheetContext) => SafeArea(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Padding(
                        padding: EdgeInsets.fromLTRB(20, 4, 20, 16),
                        child: Text(
                          'Select pet',
                          style: TextStyle(
                            fontSize: 20,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ),
                      Flexible(
                        child: ListView.builder(
                          shrinkWrap: true,
                          itemCount: pets.length,
                          itemBuilder: (_, index) {
                            final pet = pets[index];
                            final isSelected =
                                pet['pet_id'] == _selectedPetId;

                            return ListTile(
                              contentPadding:
                              const EdgeInsets.symmetric(
                                horizontal: 24,
                                vertical: 4,
                              ),
                              title: Text(pet['pet_name'] as String),
                              subtitle: Text(
                                pet['species'].toString(),
                              ),
                              selected: isSelected,
                              selectedColor: const Color(0xFF176B32),
                              selectedTileColor:
                              const Color(0xFFEAF4ED),
                              trailing: isSelected
                                  ? const Icon(
                                Icons.check,
                                color: Color(0xFF176B32),
                              )
                                  : null,
                              onTap: () {
                                Navigator.pop(sheetContext, pet);
                              },
                            );
                          },
                        ),
                      ),
                    ],
                  ),
                ),
              );

              if (!mounted || selected == null) return;

              final petId = selected['pet_id'] as int;
              if (petId == _selectedPetId) return;

              setState(() {
                _selectedPetId = petId;
                _selectedPetName = selected['pet_name'] as String;
                _page = 0;
                _future = _fetch(0);
              });
            },
            child: Padding(
              padding: const EdgeInsets.symmetric(
                horizontal: 16,
                vertical: 14,
              ),
              child: Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Selected pet',
                          style: TextStyle(
                            fontSize: 12,
                            color: Color(0xFF6B786E),
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          _selectedPetName,
                          style: const TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.w600,
                            color: Color(0xFF24372A),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const Icon(
                    Icons.keyboard_arrow_down,
                    color: Color(0xFF6B786E),
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF5F7F5),
      appBar: AppBar(
        title: const Text(
          'Medical History',
          style: TextStyle(fontWeight: FontWeight.w700),
        ),
        backgroundColor: const Color(0xFFF5F7F5),
        foregroundColor: const Color(0xFF176B32),
        surfaceTintColor: Colors.transparent,
        elevation: 0,
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
            child: _petSelector(),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Align(
              alignment: Alignment.centerLeft,
              child: Text(
                'Visit history · $_selectedPetName',
                style: Theme
                    .of(context)
                    .textTheme
                    .titleMedium,
              ),
            ),
          ),
          const SizedBox(height: 8),
          Expanded(
            child: FutureBuilder<List<Map<String, dynamic>>>(
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
                        'Completed consultations',
                        style: TextStyle(
                          color: Color(0xFF6B786E),
                          fontSize: 13,
                        ),
                      ),
                      const SizedBox(height: 12),
                      if (visible.isEmpty)
                        const Padding(
                          padding: EdgeInsets.symmetric(vertical: 32),
                          child: Text('No completed medical records yet.'),
                        ),
                      for (final record in visible) _record(record),
                      const SizedBox(height: 16),
                      if (_page > 0 || data.length > _pageSize)
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
          ),
        ],
      ),
    );
  }
}