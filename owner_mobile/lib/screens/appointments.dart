import 'package:flutter/material.dart';

import '../services/api_client.dart';
import '../services/appointment_service.dart';
import '../services/pet_service.dart';
import 'book_appointment.dart';
import 'clinic_picker.dart';
import 'emergency.dart';
import 'reschedule_appointment.dart';
import 'appointment_details.dart';
import '../services/followup_service.dart';
import 'followup_care.dart';

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

  Future<void> _openFollowupCare() async {
    if (_loading || _openingBooking) return;

    setState(() => _openingBooking = true);

    try {
      await Navigator.of(context).push<void>(
        MaterialPageRoute(
          builder: (_) => FollowupCareScreen(
            service: FollowupService(widget.service.api),
          ),
        ),
      );

      if (mounted) await _load(reset: true);
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
    if (item['status'] == 'in_progress') {
      return true;
    }

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

  Future<void> _openAppointmentDetails(
      Map<String, dynamic> item,
      ) async {
    if (_loading || _openingBooking) return;

    setState(() => _openingBooking = true);

    try {
      await Navigator.of(context).push<void>(
        MaterialPageRoute(
          builder: (_) => AppointmentDetailsScreen(
            appointment: Map<String, dynamic>.from(item),
            service: widget.service,
          ),
        ),
      );

      if (mounted) await _load(reset: true);
    } finally {
      if (mounted) {
        setState(() => _openingBooking = false);
      }
    }
  }

  Widget _appointmentCard(Map<String, dynamic> item) {
    const green = Color(0xFF176B32);
    const muted = Color(0xFF6B7770);

    final start = item['start_time'] as String;
    final end = item['end_time'] as String;
    final status = item['status'] as String;
    final rearrangement = item['needs_rearrangement'] == true;
    final followup = item['has_pending_followup'] == true;
    final busy = _loading || _openingBooking;

    final statusLabels = {
      'pending': 'Pending',
      'confirmed': 'Confirmed',
      'in_progress': 'In progress',
      'completed': 'Completed',
      'cancelled': 'Cancelled',
      'rejected': 'Rejected',
    };

    final statusColor = rearrangement
        ? const Color(0xFFB42318)
        : ['confirmed', 'completed'].contains(status)
        ? green
        : status == 'pending'
        ? const Color(0xFF946116)
        : muted;

    final statusBackground = rearrangement
        ? const Color(0xFFFFEFED)
        : ['confirmed', 'completed'].contains(status)
        ? const Color(0xFFE8F3EB)
        : status == 'pending'
        ? const Color(0xFFFFF4DE)
        : const Color(0xFFF0F2F1);

    return Card(
      color: Colors.white,
      surfaceTintColor: Colors.transparent,
      elevation: 0,
      margin: const EdgeInsets.only(bottom: 14),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(14),
        side: const BorderSide(color: Color(0xFFDDE7DF)),
      ),
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
                    style: const TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Align(
                    alignment: Alignment.topRight,
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 10,
                        vertical: 5,
                      ),
                      decoration: BoxDecoration(
                        color: statusBackground,
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Text(
                        rearrangement
                            ? 'Needs rearrangement'
                            : statusLabels[status] ??
                            status.replaceAll('_', ' '),
                        style: TextStyle(
                          color: statusColor,
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Text(
              item['clinic_name'] as String,
              style: const TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w500,
                height: 1.4,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              'Vet: ${item['veterinarian_name']}',
              style: const TextStyle(fontSize: 13, color: muted),
            ),
            const SizedBox(height: 12),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: const Color(0xFFF3F7F4),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                children: [
                  const Icon(
                    Icons.calendar_today_outlined,
                    size: 17,
                    color: green,
                  ),
                  const SizedBox(width: 9),
                  Expanded(
                    child: Text(
                      '${_dateLabel(item['appointment_date'] as String)}'
                          ' · ${start.substring(0, 5)}–${end.substring(0, 5)}',
                      style: const TextStyle(fontSize: 13),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 10),
            Text(
              (item['appointment_type'] as String).replaceAll('_', ' '),
              style: const TextStyle(fontSize: 13, color: muted),
            ),
            if ((item['clinic_address'] as String?)?.trim().isNotEmpty ==
                true) ...[
              const SizedBox(height: 6),
              Text(
                item['clinic_address'] as String,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontSize: 12, color: muted),
              ),
            ],
            if (rearrangement) ...[
              const SizedBox(height: 12),
              const Text(
                'Your vet is unavailable. Contact the clinic to '
                    'arrange another suitable time.',
                style: TextStyle(
                  color: Color(0xFFB42318),
                  fontSize: 13,
                  height: 1.4,
                ),
              ),
            ],
            if (followup) ...[
              const SizedBox(height: 10),
              const Row(
                children: [
                  Icon(
                    Icons.assignment_outlined,
                    size: 16,
                    color: Color(0xFF946116),
                  ),
                  SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      'Follow-up needed',
                      style: TextStyle(
                        fontSize: 12,
                        color: Color(0xFF946116),
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                ],
              ),
            ],
            const SizedBox(height: 12),
            const Divider(height: 1, color: Color(0xFFE8EDE9)),
            const SizedBox(height: 10),
            Row(
              children: [
                TextButton.icon(
                  onPressed: busy
                      ? null
                      : () => _openAppointmentDetails(item),
                  style: TextButton.styleFrom(
                    foregroundColor: green,
                    backgroundColor: const Color(0xFFEDF5EF),
                    padding: const EdgeInsets.symmetric(
                      horizontal: 12,
                      vertical: 9,
                    ),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(8),
                    ),
                  ),
                  icon: const Icon(
                    Icons.description_outlined,
                    size: 18,
                  ),
                  label: Text(
                    followup ? 'View follow-up' : 'View details',
                  ),
                ),
                const Spacer(),
                if (_canChangeAppointment(item))
                  PopupMenuButton<String>(
                    enabled: !busy,
                    tooltip: 'Appointment actions',
                    icon: const Icon(Icons.more_horiz, color: muted),
                    onSelected: (value) async {
                      if (value == 'reschedule') {
                        await _rescheduleAppointment(item);
                      } else if (value == 'cancel') {
                        await _cancelAppointment(item);
                      }
                    },
                    itemBuilder: (_) => [
                      if (item['appointment_type'] != 'emergency')
                        const PopupMenuItem(
                          value: 'reschedule',
                          child: Text('Reschedule'),
                        ),
                      const PopupMenuItem(
                        value: 'cancel',
                        child: Text(
                          'Cancel appointment',
                          style: TextStyle(color: Color(0xFFB42318)),
                        ),
                      ),
                    ],
                  ),
              ],
            ),
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
                : _openFollowupCare,
            icon: const Icon(Icons.assignment_outlined),
            label: const Text('Follow-up Care'),
            style: OutlinedButton.styleFrom(
              minimumSize: const Size.fromHeight(44),
              foregroundColor: const Color(0xFF176B32),
              side: const BorderSide(color: Color(0xFFCBDCCF)),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(10),
              ),
            ),
          ),
          const SizedBox(height: 8),
          OutlinedButton.icon(
            onPressed: _loading || _openingBooking
                ? null
                : _openEmergencyRequests,
            icon: const Icon(Icons.emergency_outlined),
            label: const Text('Emergency requests'),
            style: OutlinedButton.styleFrom(
              minimumSize: const Size.fromHeight(44),
              foregroundColor: const Color(0xFF176B32),
              side: const BorderSide(color: Color(0xFFCBDCCF)),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(10),
              ),
            ),
          ),
          const SizedBox(height: 20),

          DropdownButtonFormField<String>(
            initialValue: _filter,
            decoration: InputDecoration(
              labelText: 'Show appointments',
              filled: true,
              fillColor: Colors.white,
              contentPadding: const EdgeInsets.symmetric(
                horizontal: 14,
                vertical: 12,
              ),
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(10),
                borderSide: const BorderSide(
                  color: Color(0xFFCBDCCF),
                ),
              ),
              enabledBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(10),
                borderSide: const BorderSide(
                  color: Color(0xFFCBDCCF),
                ),
              ),
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
            onChanged: _loading || _openingBooking
                ? null
                : (value) {
              if (value == null || value == _filter) return;

              setState(() => _filter = value);
              _load(reset: true);
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