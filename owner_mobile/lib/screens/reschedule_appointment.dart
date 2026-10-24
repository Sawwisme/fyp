import 'package:flutter/material.dart';

import '../services/api_client.dart';
import '../services/appointment_service.dart';

class RescheduleAppointmentScreen extends StatefulWidget {
  final AppointmentService service;
  final Map<String, dynamic> appointment;

  const RescheduleAppointmentScreen({
    super.key,
    required this.service,
    required this.appointment,
  });

  @override
  State<RescheduleAppointmentScreen> createState() =>
      _RescheduleAppointmentScreenState();
}

class _RescheduleAppointmentScreenState
    extends State<RescheduleAppointmentScreen> {
  List<Map<String, dynamic>> _vets = [];
  List<Map<String, dynamic>> _slots = [];

  int? _vetId;
  int? _slotId;
  late DateTime _date;

  bool _loading = true;
  bool _loadingSlots = false;
  bool _saving = false;
  bool _uncertain = false;

  String? _error;
  String? _slotError;
  int _slotVersion = 0;

  @override
  void initState() {
    super.initState();

    _date = DateTime.parse(
      widget.appointment['appointment_date'] as String,
    );
    _vetId = widget.appointment['veterinarian_id'] as int;

    _loadVets();
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

  Future<void> _loadVets() async {
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final vets = <Map<String, dynamic>>[];

      for (var offset = 0; ; offset += 100) {
        final page = await widget.service.getVeterinarians(
          clinicId: widget.appointment['clinic_id'] as int,
          offset: offset,
          limit: 100,
        );

        if (!mounted) return;

        vets.addAll(page);
        if (page.length < 100) break;
      }

      setState(() {
        _vets = vets;

        if (!vets.any(
              (vet) => vet['veterinarian_id'] == _vetId,
        )) {
          _vetId = vets.isEmpty
              ? null
              : vets.first['veterinarian_id'] as int;
        }
      });

      await _loadSlots();
    } on ApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } catch (_) {
      if (mounted) {
        setState(() => _error = 'Could not load veterinarians.');
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _loadSlots() async {
    final version = ++_slotVersion;
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
      final slots = <Map<String, dynamic>>[];

      for (var offset = 0; ; offset += 100) {
        final page = await widget.service.getAvailableSlots(
          veterinarianId: vetId,
          date: selectedDate,
          offset: offset,
          limit: 100,
        );

        if (!mounted || version != _slotVersion) return;

        slots.addAll(page);
        if (page.length < 100) break;
      }

      setState(() => _slots = slots);
    } on ApiException catch (error) {
      if (mounted && version == _slotVersion) {
        setState(() => _slotError = error.message);
      }
    } catch (_) {
      if (mounted && version == _slotVersion) {
        setState(() => _slotError = 'Could not load slots.');
      }
    } finally {
      if (mounted && version == _slotVersion) {
        setState(() => _loadingSlots = false);
      }
    }
  }

  Future<void> _chooseDate() async {
    final first = _today();

    final selected = await showDatePicker(
      context: context,
      initialDate: _date.isBefore(first) ? first : _date,
      firstDate: first,
      lastDate: DateTime(first.year + 1, first.month, first.day),
    );

    if (!mounted || selected == null) return;

    setState(() => _date = selected);
    await _loadSlots();
  }

  Future<void> _save() async {
    if (_saving || _loadingSlots || _uncertain || _slotId == null) {
      return;
    }

    final selectedSlot = _slots.firstWhere(
          (slot) => slot['time_slot_id'] == _slotId,
    );
    final selectedVet = _vets.firstWhere(
          (vet) => vet['veterinarian_id'] == _vetId,
    );

    setState(() {
      _saving = true;
      _error = null;
    });

    try {
      final confirmed = await showDialog<bool>(
        context: context,
        builder: (dialogContext) => AlertDialog(
          title: const Text('Confirm new appointment time'),
          content: Text(
            '${widget.appointment['pet_name']}\n'
                '${selectedVet['full_name']}\n'
                '${_dateLabel(_date)} · ${_timeLabel(selectedSlot)}',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogContext, false),
              child: const Text('Back'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(dialogContext, true),
              child: const Text('Confirm change'),
            ),
          ],
        ),
      );

      if (!mounted || confirmed != true) return;

      await widget.service.rescheduleAppointment(
        appointmentId: widget.appointment['appointment_id'] as int,
        timeSlotId: _slotId!,
      );

      if (!mounted) return;

      setState(() => _saving = false);
      Navigator.of(context).pop(true);
    } on ApiException catch (error) {
      if (!mounted) return;

      setState(() {
        _error = error.message;
        _uncertain = error.statusCode == null;
      });

      if (error.statusCode == 400 || error.statusCode == 409) {
        await _loadSlots();
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          _uncertain = true;
          _error = 'Could not confirm the change. '
              'Check My Appointments before trying again.';
        });
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Widget _body() {
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_vets.isEmpty || (_error != null && _vetId == null)) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                _error ?? 'No veterinarians available at this clinic.',
                textAlign: TextAlign.center,
              ),
              OutlinedButton(
                onPressed: _loadVets,
                child: const Text('Try again'),
              ),
            ],
          ),
        ),
      );
    }

    final disabled = _saving || _uncertain;
    final oldStart = widget.appointment['start_time'] as String;

    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        Text(
          widget.appointment['clinic_name'] as String,
          style: Theme.of(context).textTheme.titleLarge,
        ),
        const SizedBox(height: 8),
        Text('Pet: ${widget.appointment['pet_name']}'),
        Text(
          'Current booking: '
              '${widget.appointment['appointment_date']} · '
              '${oldStart.substring(0, 5)}',
        ),
        const SizedBox(height: 16),
        const Text(
          'Your original booking stays reserved until '
              'the change succeeds. All times use Malaysia time.',
        ),
        const SizedBox(height: 24),

        DropdownButtonFormField<int>(
          key: ValueKey(_vetId),
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
          onChanged: disabled
              ? null
              : (value) {
            setState(() => _vetId = value);
            _loadSlots();
          },
        ),

        const SizedBox(height: 16),

        OutlinedButton.icon(
          onPressed: disabled ? null : _chooseDate,
          icon: const Icon(Icons.calendar_month),
          label: Text(_dateLabel(_date)),
        ),

        const SizedBox(height: 20),

        if (_loadingSlots)
          const Center(child: CircularProgressIndicator())
        else if (_slotError != null) ...[
          Text(_slotError!),
          TextButton(
            onPressed: disabled ? null : _loadSlots,
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
                onSelected: disabled
                    ? null
                    : (selected) {
                  setState(() => _slotId = selected ? id : null);
                },
              );
            }).toList(),
          ),

        if (_error != null) ...[
          const SizedBox(height: 16),
          Text(
            _error!,
            style: TextStyle(
              color: Theme.of(context).colorScheme.error,
            ),
          ),
        ],

        const SizedBox(height: 24),

        FilledButton(
          onPressed: disabled || _loadingSlots || _slotId == null
              ? null
              : _save,
          child: Text(_saving ? 'Please wait…' : 'Review change'),
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: !_saving,
      child: Scaffold(
        appBar: AppBar(title: const Text('Reschedule appointment')),
        body: SafeArea(child: _body()),
      ),
    );
  }
}