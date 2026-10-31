import 'package:flutter/material.dart';

import '../services/api_client.dart';
import '../services/appointment_service.dart';
import '../services/pet_service.dart';
import 'pet_form.dart';

class BookAppointmentScreen extends StatefulWidget {
  final Map<String, dynamic> clinic;
  final AppointmentService service;
  final PetService petService;
  final Map<String, dynamic>? followupContext;


  const BookAppointmentScreen({
    super.key,
    required this.clinic,
    required this.service,
    required this.petService,
    this.followupContext,
  });

  @override
  State<BookAppointmentScreen> createState() =>
      _BookAppointmentScreenState();
}

class _BookAppointmentScreenState extends State<BookAppointmentScreen> {
  List<Map<String, dynamic>> _pets = [];
  List<Map<String, dynamic>> _vets = [];
  List<Map<String, dynamic>> _slots = [];

  int? _petId;
  int? _vetId;
  int? _slotId;

  String _type = 'dental_checkup';
  late DateTime _date;

  bool _loading = true;
  bool _loadingSlots = false;
  bool _saving = false;
  bool _uncertainBooking = false;

  String? _error;
  String? _slotError;
  int _slotVersion = 0;

  @override
  void initState() {
    super.initState();
    _date = _today();
    _loadOptions();
  }

  DateTime _today() {
    final malaysia = DateTime.now().toUtc().add(
      const Duration(hours: 8),
    );

    return DateTime(
      malaysia.year,
      malaysia.month,
      malaysia.day,
    );
  }

  String _dateLabel(DateTime value) {
    return '${value.day.toString().padLeft(2, '0')}/'
        '${value.month.toString().padLeft(2, '0')}/'
        '${value.year}';
  }

  String _timeLabel(Map<String, dynamic> slot) {
    final start = slot['start_time'] as String;
    final end = slot['end_time'] as String;

    return '${start.substring(0, 5)}–${end.substring(0, 5)}';
  }

  Future<List<Map<String, dynamic>>> _allPages(
      Future<List<Map<String, dynamic>>> Function(int offset) fetch,
      ) async {
    final collected = <Map<String, dynamic>>[];

    for (var offset = 0; ; offset += 100) {
      final page = await fetch(offset);
      collected.addAll(page);

      if (page.length < 100) break;
    }

    return collected;
  }

  Future<void> _loadOptions() async {
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final followup = widget.followupContext;

      if (followup != null) {
        setState(() {
          _pets = [
            {
              'pet_id': followup['pet_id'],
              'pet_name': followup['pet_name'],
            },
          ];

          _vets = [
            {
              'veterinarian_id': followup['veterinarian_id'],
              'full_name': followup['veterinarian_name'],
            },
          ];

          _petId = followup['pet_id'] as int;
          _vetId = followup['veterinarian_id'] as int;
          _type = 'follow_up';
        });

        await _loadSlots();
        return;
      }

      final results = await Future.wait([
        _allPages(
              (offset) => widget.petService.getPets(
            offset: offset,
            limit: 100,
          ),
        ),
        _allPages(
              (offset) => widget.service.getVeterinarians(
            clinicId: widget.clinic['clinic_id'] as int,
            offset: offset,
            limit: 100,
          ),
        ),
      ]);

      if (!mounted) return;

      setState(() {
        _pets = results[0];
        _vets = results[1];

        if (!_pets.any((item) => item['pet_id'] == _petId)) {
          _petId = _pets.isEmpty ? null : _pets.first['pet_id'] as int;
        }

        if (!_vets.any((item) => item['veterinarian_id'] == _vetId)) {
          _vetId = _vets.isEmpty
              ? null
              : _vets.first['veterinarian_id'] as int;
        }
      });

      await _loadSlots();
    } on ApiException catch (error) {
      if (mounted) {
        setState(() => _error = error.message);
      }
    } catch (_) {
      if (mounted) {
        setState(() => _error = 'Could not load booking options.');
      }
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  Future<void> _loadSlots() async {
    final currentVersion = ++_slotVersion;
    final vetId = _vetId;
    final selectedDate = _date;

    setState(() {
      _slots = [];
      _slotId = null;
      _slotError = null;
      _loadingSlots = vetId != null;
    });

    if (vetId == null) return;

    try {
      final slots = await _allPages(
            (offset) => widget.service.getAvailableSlots(
          veterinarianId: vetId,
          date: selectedDate,
          offset: offset,
          limit: 100,
        ),
      );

      if (!mounted || currentVersion != _slotVersion) return;

      setState(() => _slots = slots);
    } on ApiException catch (error) {
      if (mounted && currentVersion == _slotVersion) {
        setState(() => _slotError = error.message);
      }
    } catch (_) {
      if (mounted && currentVersion == _slotVersion) {
        setState(() => _slotError = 'Could not load available slots.');
      }
    } finally {
      if (mounted && currentVersion == _slotVersion) {
        setState(() => _loadingSlots = false);
      }
    }
  }

  Future<void> _selectDate() async {
    final first = _today();
    final initial = _date.isBefore(first) ? first : _date;

    final selected = await showDatePicker(
      context: context,
      initialDate: initial,
      firstDate: first,
      lastDate: DateTime(first.year + 1, first.month, first.day),
    );

    if (!mounted || selected == null) return;

    setState(() => _date = selected);
    await _loadSlots();
  }

  Future<void> _addPet() async {
    final created = await Navigator.of(context).push<bool>(
      MaterialPageRoute(
        builder: (_) => PetFormScreen(service: widget.petService),
      ),
    );

    if (!mounted || created != true) return;

    await _loadOptions();
  }

  Future<void> _book() async {
    if (_saving || _loadingSlots || _uncertainBooking ||
        _petId == null || _vetId == null || _slotId == null) {
      return;
    }

    final pet = _pets.firstWhere(
          (item) => item['pet_id'] == _petId,
    );
    final vet = _vets.firstWhere(
          (item) => item['veterinarian_id'] == _vetId,
    );
    final slot = _slots.firstWhere(
          (item) => item['time_slot_id'] == _slotId,
    );

    setState(() {
      _saving = true;
      _error = null;
    });

    try {
      final confirmed = await showDialog<bool>(
        context: context,
        builder: (dialogContext) => AlertDialog(
          title: const Text('Confirm appointment'),
          content: Text(
            '${widget.clinic['clinic_name']}\n'
                'Pet: ${pet['pet_name']}\n'
                'Vet: ${vet['full_name']}\n'
                'Date: ${_dateLabel(_date)}\n'
                'Time: ${_timeLabel(slot)}\n'
                'Type: ${_type.replaceAll('_', ' ')}',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogContext, false),
              child: const Text('Back'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(dialogContext, true),
              child: const Text('Confirm booking'),
            ),
          ],
        ),
      );

      if (!mounted || confirmed != true) return;

      await widget.service.createAppointment(
        petId: _petId!,
        timeSlotId: _slotId!,
        appointmentType: _type,
        followupCareId:
        widget.followupContext?['followup_care_id'] as int?,
      );

      if (!mounted) return;

      // Allow the route to close after saving has finished.
      setState(() => _saving = false);
      Navigator.of(context).pop(true);
    } on ApiException catch (error) {
      if (!mounted) return;

      setState(() {
        _error = error.message;
        _uncertainBooking = error.statusCode == null;
      });

      if (error.statusCode == 409 || error.statusCode == 400) {
        await _loadSlots();
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          _uncertainBooking = true;
          _error = 'Could not confirm the booking. '
              'Check My Appointments before trying again.';
        });
      }
    } finally {
      if (mounted) {
        setState(() => _saving = false);
      }
    }
  }

  Widget _body() {
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_pets.isEmpty || _vets.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                _error ??
                    (_pets.isEmpty
                        ? 'Add a pet before booking an appointment.'
                        : 'This clinic has no available veterinarians.'),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 16),
              if (_error == null && _pets.isEmpty)
                FilledButton(
                  onPressed: _addPet,
                  child: const Text('Add pet'),
                ),
              OutlinedButton(
                onPressed: _loadOptions,
                child: const Text('Try again'),
              ),
            ],
          ),
        ),
      );
    }

    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        Text(
          widget.clinic['clinic_name'] as String,
          style: Theme.of(context).textTheme.titleLarge,
        ),
        const SizedBox(height: 8),
        Text(
          widget.clinic['address'] as String? ??
              'Address not provided',
        ),
        const SizedBox(height: 24),

        DropdownButtonFormField<int>(
          key: ValueKey('pet-$_petId'),
          initialValue: _petId,
          decoration: const InputDecoration(
            labelText: 'Pet',
            border: OutlineInputBorder(),
          ),
          items: _pets.map((pet) {
            return DropdownMenuItem<int>(
              value: pet['pet_id'] as int,
              child: Text(pet['pet_name'] as String),
            );
          }).toList(),
          onChanged: widget.followupContext != null ||
              _saving ||
              _uncertainBooking
              ? null
              : (value) => setState(() => _petId = value),
        ),
        const SizedBox(height: 16),

        DropdownButtonFormField<int>(
          key: ValueKey('vet-$_vetId'),
          initialValue: _vetId,
          isExpanded: true,
          decoration: const InputDecoration(
            labelText: 'Veterinarian',
            border: OutlineInputBorder(),
          ),
          items: _vets.map((vet) {
            return DropdownMenuItem<int>(
              value: vet['veterinarian_id'] as int,
              child: Text(
                vet['full_name'] as String,
                overflow: TextOverflow.ellipsis,
              ),
            );
          }).toList(),
          onChanged: widget.followupContext != null ||
              _saving ||
              _uncertainBooking
              ? null
              : (value) {
            setState(() => _vetId = value);
            _loadSlots();
          },
        ),
        const SizedBox(height: 16),

        DropdownButtonFormField<String>(
          initialValue: _type,
          decoration: const InputDecoration(
            labelText: 'Appointment type',
            border: OutlineInputBorder(),
          ),
          items: const [
            DropdownMenuItem(
              value: 'dental_checkup',
              child: Text('Dental checkup'),
            ),
            DropdownMenuItem(
              value: 'consultation',
              child: Text('Consultation'),
            ),
            DropdownMenuItem(
              value: 'follow_up',
              child: Text('Follow-up'),
            ),
          ],
          onChanged: widget.followupContext != null ||
              _saving ||
              _uncertainBooking
              ? null
              : (value) {
            if (value != null) setState(() => _type = value);
          },
        ),
        const SizedBox(height: 16),

        OutlinedButton.icon(
          onPressed: _saving || _uncertainBooking ? null : _selectDate,
          icon: const Icon(Icons.calendar_month),
          label: Text(_dateLabel(_date)),
        ),
        const Text('All appointment times use Malaysia time.'),
        const SizedBox(height: 20),

        Text(
          'Available slots',
          style: Theme.of(context).textTheme.titleMedium,
        ),
        const SizedBox(height: 12),

        if (_loadingSlots)
          const Center(child: CircularProgressIndicator())
        else if (_slotError != null) ...[
          Text(_slotError!),
          TextButton(
            onPressed: _saving || _uncertainBooking ? null : _loadSlots,
            child: const Text('Retry loading slots'),
          ),
        ] else if (_slots.isEmpty)
          const Text(
            'No available slots. Choose another date or veterinarian.',
          )
        else
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: _slots.map((slot) {
              final id = slot['time_slot_id'] as int;

              return ChoiceChip(
                label: Text(_timeLabel(slot)),
                selected: _slotId == id,
                onSelected: _saving || _uncertainBooking
                    ? null
                    : (selected) {
                  setState(() => _slotId = selected ? id : null);
                },
              );
            }).toList(),
          ),

        if (_error != null) ...[
          const SizedBox(height: 20),
          Text(
            _error!,
            style: TextStyle(
              color: Theme.of(context).colorScheme.error,
            ),
          ),
        ],

        const SizedBox(height: 24),
        FilledButton(
          onPressed: _saving || _loadingSlots ||
              _uncertainBooking || _slotId == null
              ? null
              : _book,
          child: Text(
            _saving ? 'Please wait…' : 'Review appointment',
          ),
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: !_saving,
      child: Scaffold(
        appBar: AppBar(title: const Text('Book appointment')),
        body: SafeArea(child: _body()),
      ),
    );
  }
}