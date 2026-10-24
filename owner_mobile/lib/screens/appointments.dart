import 'package:flutter/material.dart';

import '../services/api_client.dart';
import '../services/appointment_service.dart';
import '../services/pet_service.dart';
import 'book_appointment.dart';
import 'clinic_picker.dart';
import 'emergency.dart';
import 'reschedule_appointment.dart';

class AppointmentsPage extends StatefulWidget {
  final AppointmentService service;
  final PetService petService;

  const AppointmentsPage({
    super.key,
    required this.service,
    required this.petService,
  });

  @override
  State<AppointmentsPage> createState() => _AppointmentsPageState();
}

class _AppointmentsPageState extends State<AppointmentsPage> {
  final List<Map<String, dynamic>> _appointments = [];

  bool _loading = false;
  bool _hasMore = true;
  bool _openingBooking = false;
  String? _error;
  String _filter = 'all';

  @override
  void initState() {
    super.initState();
    _load(reset: true);
  }

  Future<void> _load({bool reset = false}) async {
    if (_loading) return;

    setState(() {
      _loading = true;
      _error = null;

      if (reset) {
        _appointments.clear();
        _hasMore = true;
      }
    });

    try {
      final page = await widget.service.getMyAppointments(
        offset: _appointments.length,
        limit: 20,
      );

      if (!mounted) return;

      setState(() {
        _appointments.addAll(page);
        _hasMore = page.length == 20;
      });
    } on ApiException catch (error) {
      if (mounted) {
        setState(() => _error = error.message);
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          _error = 'Could not load your appointments.';
        });
      }
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  Future<void> _openEmergencyRequests() async {
    if (_openingBooking) return;

    setState(() => _openingBooking = true);

    try {
      await Navigator.of(context).push<void>(
        MaterialPageRoute(
          builder: (_) => EmergencyRequestsScreen(
            service: widget.service,
            petService: widget.petService,
          ),
        ),
      );

      if (!mounted) return;

      await _load(reset: true);
    } finally {
      if (mounted) {
        setState(() => _openingBooking = false);
      }
    }
  }

  Future<void> _startBooking() async {
    if (_openingBooking) return;

    setState(() => _openingBooking = true);

    try {
      final clinic =
      await Navigator.of(context).push<Map<String, dynamic>>(
        MaterialPageRoute(
          builder: (_) => ClinicPickerScreen(
            service: widget.service,
          ),
        ),
      );

      if (!mounted || clinic == null) return;

      final created = await Navigator.of(context).push<bool>(
        MaterialPageRoute(
          builder: (_) => BookAppointmentScreen(
            clinic: clinic,
            service: widget.service,
            petService: widget.petService,
          ),
        ),
      );

      if (!mounted) return;

      // Refresh even after leaving an uncertain booking response.
      await _load(reset: true);

      if (!mounted || created != true) return;

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Appointment booked successfully.'),
        ),
      );
    } finally {
      if (mounted) {
        setState(() => _openingBooking = false);
      }
    }
  }

  bool _canChangeAppointment(Map<String, dynamic> item) {
    if (!['pending', 'confirmed'].contains(item['status'])) {
      return false;
    }

    final start = DateTime.parse(
      '${item['appointment_date']}T${item['start_time']}+08:00',
    );

    return start.isAfter(DateTime.now());
  }

  Future<void> _cancelAppointment(Map<String, dynamic> item) async {
    if (_loading || _openingBooking) return;

    setState(() => _openingBooking = true);

    var attempted = false;
    String? outcome;

    try {
      final confirmed = await showDialog<bool>(
        context: context,
        builder: (dialogContext) => AlertDialog(
          title: const Text('Cancel appointment?'),
          content: Text(
            'Cancel ${item['pet_name']}’s appointment at '
                '${item['clinic_name']} on '
                '${_dateLabel(item['appointment_date'] as String)}?',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogContext, false),
              child: const Text('Keep appointment'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(dialogContext, true),
              child: const Text('Cancel appointment'),
            ),
          ],
        ),
      );

      if (!mounted || confirmed != true) return;

      attempted = true;

      await widget.service.cancelAppointment(
        item['appointment_id'] as int,
      );

      outcome = 'Appointment cancelled.';
    } on ApiException catch (error) {
      outcome = error.message;
    } catch (_) {
      outcome = 'Could not confirm cancellation. '
          'Refresh to check the latest status.';
    } finally {
      if (mounted && attempted) {
        await _load(reset: true);
      }

      if (mounted) {
        setState(() => _openingBooking = false);

        if (outcome != null) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(outcome!)),
          );
        }
      }
    }
  }

  bool _isUpcoming(Map<String, dynamic> item) {
    if (!['pending', 'confirmed'].contains(item['status'])) {
      return false;
    }

    final end = DateTime.parse(
      '${item['appointment_date']}T${item['end_time']}+08:00',
    );

    return end.isAfter(DateTime.now());
  }

  String _dateLabel(String value) {
    final date = DateTime.parse(value);
    return '${date.day.toString().padLeft(2, '0')}/'
        '${date.month.toString().padLeft(2, '0')}/'
        '${date.year}';
  }

  Future<void> _rescheduleAppointment(
      Map<String, dynamic> item,
      ) async {
    if (_loading || _openingBooking) return;

    setState(() => _openingBooking = true);

    try {
      final changed = await Navigator.of(context).push<bool>(
        MaterialPageRoute(
          builder: (_) => RescheduleAppointmentScreen(
            service: widget.service,
            appointment: item,
          ),
        ),
      );

      if (!mounted) return;

      await _load(reset: true);

      if (!mounted || changed != true) return;

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Appointment rescheduled.')),
      );
    } finally {
      if (mounted) {
        setState(() => _openingBooking = false);
      }
    }
  }

  Widget _appointmentCard(Map<String, dynamic> item) {
    final start = item['start_time'] as String;
    final end = item['end_time'] as String;

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: Text(
                    item['pet_name'] as String,
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                ),
                const SizedBox(width: 12),
                Text(
                  (item['status'] as String).replaceAll('_', ' '),
                  style: const TextStyle(
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Text(item['clinic_name'] as String),
            Text('Vet: ${item['veterinarian_name']}'),
            const SizedBox(height: 8),
            Text(
              '${_dateLabel(item['appointment_date'] as String)}'
                  ' · ${start.substring(0, 5)}–${end.substring(0, 5)}',
            ),
            const SizedBox(height: 6),
            Text(
              (item['appointment_type'] as String)
                  .replaceAll('_', ' '),
            ),
            if (item['clinic_address'] != null) ...[
              const SizedBox(height: 8),
              Text(item['clinic_address'] as String),
            ],

            if (_canChangeAppointment(item)) ...[
              const SizedBox(height: 16),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  if (item['appointment_type'] != 'emergency')
                    OutlinedButton(
                      onPressed: _loading || _openingBooking
                          ? null
                          : () => _rescheduleAppointment(item),
                      child: const Text('Reschedule'),
                    ),
                  OutlinedButton(
                    onPressed: _loading || _openingBooking
                        ? null
                        : () => _cancelAppointment(item),
                    child: const Text('Cancel appointment'),
                  ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final visible = _appointments.where((item) {
      if (_filter == 'upcoming') return _isUpcoming(item);
      if (_filter == 'history') return !_isUpcoming(item);
      return true;
    }).toList();

    return RefreshIndicator(
      onRefresh: () async {
        if (!_openingBooking) {
          await _load(reset: true);
        }
      },
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(20),
        children: [
          Text(
            'My Appointments',
            style: Theme.of(context).textTheme.headlineSmall,
          ),
          const SizedBox(height: 8),
          const Text('All appointment times use Malaysia time.'),
          const SizedBox(height: 16),

          FilledButton.icon(
            onPressed: _loading || _openingBooking
                ? null
                : _startBooking,
            icon: const Icon(Icons.add),
            label: const Text('Book appointment'),
          ),
          const SizedBox(height: 8),
          OutlinedButton.icon(
            onPressed: _loading || _openingBooking
                ? null
                : _openEmergencyRequests,
            icon: const Icon(Icons.emergency_outlined),
            label: const Text('Emergency requests'),
          ),
          const SizedBox(height: 20),

          DropdownButtonFormField<String>(
            initialValue: _filter,
            decoration: const InputDecoration(
              labelText: 'Show appointments',
              border: OutlineInputBorder(),
            ),
            items: const [
              DropdownMenuItem(
                value: 'all',
                child: Text('All appointments'),
              ),
              DropdownMenuItem(
                value: 'upcoming',
                child: Text('Upcoming'),
              ),
              DropdownMenuItem(
                value: 'history',
                child: Text('History'),
              ),
            ],
            onChanged: (value) {
              if (value != null) {
                setState(() => _filter = value);
              }
            },
          ),
          const SizedBox(height: 16),

          if (_error != null) ...[
            Text(
              _error!,
              style: TextStyle(
                color: Theme.of(context).colorScheme.error,
              ),
            ),
            TextButton(
              onPressed: _loading || _openingBooking
                  ? null
                  : () => _load(reset: _appointments.isEmpty),
              child: const Text('Try again'),
            ),
          ],

          ...visible.map(_appointmentCard),

          if (!_loading && _error == null && visible.isEmpty)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 24),
              child: Text(
                _appointments.isEmpty
                    ? 'No appointments yet. Select Book appointment to begin.'
                    : 'No matching appointments among the loaded records.',
                textAlign: TextAlign.center,
              ),
            ),

          if (_appointments.isNotEmpty)
            Text(
              'Showing ${visible.length} of '
                  '${_appointments.length} loaded appointments.',
            ),

          if (_loading)
            const Padding(
              padding: EdgeInsets.all(20),
              child: Center(child: CircularProgressIndicator()),
            )
          else if (_hasMore && _error == null)
            TextButton(
              onPressed: _openingBooking ? null : () => _load(),
              child: const Text('Load more'),
            ),
        ],
      ),
    );
  }
}