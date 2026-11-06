import 'package:flutter/material.dart';

import '../services/api_client.dart';
import '../services/followup_service.dart';
import 'followup_updates.dart';
import '../services/appointment_service.dart';
import '../services/pet_service.dart';
import 'book_appointment.dart';

class FollowupCareScreen extends StatefulWidget {
  final FollowupService service;

  const FollowupCareScreen({
    super.key,
    required this.service,
  });

  @override
  State<FollowupCareScreen> createState() =>
      _FollowupCareScreenState();
}

class _FollowupCareScreenState extends State<FollowupCareScreen> {
  static const _pageSize = 10;
  static const _green = Color(0xFF2549C7);

  late Future<List<Map<String, dynamic>>> _future;
  String _filter = 'pending';
  int _page = 0;
  bool _opening = false;

  @override
  void initState() {
    super.initState();
    _future = _fetch();
  }

  Future<List<Map<String, dynamic>>> _fetch() {
    return widget.service.getFollowups(
      status: _filter == 'all' ? null : _filter,
      offset: _page * _pageSize,
      limit: _pageSize + 1,
    );
  }

  void _load(int page) {
    setState(() {
      _page = page;
      _future = _fetch();
    });
  }

  Future<void> _refresh() async {
    _load(0);
    try {
      await _future;
    } catch (_) {
      // FutureBuilder displays the error.
    }
  }

  String _date(dynamic value) {
    final date = DateTime.tryParse(value?.toString() ?? '');
    if (date == null) return 'Not set';

    return '${date.day.toString().padLeft(2, '0')}/'
        '${date.month.toString().padLeft(2, '0')}/'
        '${date.year}';
  }

  Future<void> _open(Map<String, dynamic> item) async {
    if (_opening) return;

    setState(() => _opening = true);

    try {
      await Navigator.of(context).push<void>(
        MaterialPageRoute(
          builder: (_) => FollowupUpdatesScreen(
            followup: item,
            service: widget.service,
          ),
        ),
      );

      if (mounted) await _refresh();
    } finally {
      if (mounted) setState(() => _opening = false);
    }
  }

  Future<void> _bookReview(Map<String, dynamic> item) async {
    if (_opening) return;

    setState(() => _opening = true);

    try {
      final booking = await widget.service.getBookingContext(
        item['followup_care_id'] as int,
      );

      if (!mounted) return;

      if (booking['existing_appointment_id'] != null) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              'Review appointment #${booking['existing_appointment_id']} '
                  'is already booked. Open My Appointments to view it.',
            ),
          ),
        );
        return;
      }

      await Navigator.of(context).push<bool>(
        MaterialPageRoute(
          builder: (_) => BookAppointmentScreen(
            clinic: {
              'clinic_id': booking['clinic_id'],
              'clinic_name': booking['clinic_name'],
            },
            service: AppointmentService(widget.service.api),
            petService: PetService(widget.service.api),
            followupContext: booking,
          ),
        ),
      );
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              error is ApiException
                  ? error.message
                  : 'Could not open follow-up booking.',
            ),
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _opening = false);
        await _refresh();
      }
    }
  }

  Widget _card(Map<String, dynamic> item) {
    final status = item['status'] as String;
    final completed = status == 'completed';

    final stageLabel = {
      'action_needed': 'Awaiting your update',
      'awaiting_review': 'Awaiting vet review',
      'update_requested': 'Another update requested',
      'visit_required': 'In-clinic review required',
      'reviewed': 'Reviewed — awaiting vet decision',
      'completed': 'Completed',
      'cancelled': 'Cancelled',
    }[item['submission_state']];

    return Card(
      color: Colors.white,
      surfaceTintColor: Colors.transparent,
      elevation: 0,
      margin: const EdgeInsets.only(bottom: 12),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: const BorderSide(color: Color(0xFFD3DCE5)),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
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
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 10,
                    vertical: 5,
                  ),
                  decoration: BoxDecoration(
                    color: completed
                        ? const Color(0xFFE8F3EB)
                        : const Color(0xFFF0F3F1),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Text(
                    {
                      'pending': 'Ongoing',
                      'completed': 'Completed',
                      'cancelled': 'Cancelled',
                    }[status] ?? status,
                    style: const TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),

            if (stageLabel != null) ...[
              Text(
                stageLabel,
                style: const TextStyle(
                  color: _green,
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: 8),
            ],

            Text(
              item['clinic_name'] as String,
              style: const TextStyle(fontWeight: FontWeight.w500),
            ),
            const SizedBox(height: 6),
            Text('Original visit: ${_date(item['appointment_date'])}'),
            Text('Review due: ${_date(item['recommended_date'])}'),
            if (item['reason'] != null) ...[
              const SizedBox(height: 10),
              Text(item['reason'] as String),
            ],
            if (item['visit_required'] == true) ...[
              const SizedBox(height: 10),
              const Text(
                'In-clinic review required',
                style: TextStyle(
                  color: _green,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
            const SizedBox(height: 14),
            if (status == 'pending' && item['visit_required'] == true) ...[
              FilledButton.icon(
                onPressed: _opening ? null : () => _bookReview(item),
                icon: const Icon(Icons.calendar_month_outlined),
                label: const Text('Book review appointment'),
              ),
              const SizedBox(height: 8),
            ],
            OutlinedButton(
              onPressed: _opening ? null : () => _open(item),
              child: Text(
                status == 'pending'
                    ? 'View instructions & updates'
                    : 'View history & feedback',
              ),
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFEEF1F5),
      appBar: AppBar(
        title: const Text('Follow-up Care'),
        backgroundColor: const Color(0xFFEEF1F5),
        foregroundColor: _green,
        surfaceTintColor: Colors.transparent,
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: DropdownButtonFormField<String>(
              initialValue: _filter,
              decoration: const InputDecoration(
                labelText: 'Show follow-ups',
                border: OutlineInputBorder(),
              ),
              items: const [
                DropdownMenuItem(value: 'pending', child: Text('Ongoing')),
                DropdownMenuItem(
                  value: 'completed',
                  child: Text('Completed'),
                ),
                DropdownMenuItem(
                  value: 'cancelled',
                  child: Text('Cancelled'),
                ),
                DropdownMenuItem(value: 'all', child: Text('All')),
              ],
              onChanged: _opening
                  ? null
                  : (value) {
                if (value == null || value == _filter) return;
                _filter = value;
                _load(0);
              },
            ),
          ),
          Expanded(
            child: FutureBuilder<List<Map<String, dynamic>>>(
              future: _future,
              builder: (context, snapshot) {
                if (snapshot.connectionState != ConnectionState.done) {
                  return const Center(child: CircularProgressIndicator());
                }

                if (snapshot.hasError) {
                  final error = snapshot.error;
                  return Center(
                    child: Padding(
                      padding: const EdgeInsets.all(24),
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Text(
                            error is ApiException
                                ? error.message
                                : 'Could not load follow-up care.',
                          ),
                          TextButton(
                            onPressed: () => _load(_page),
                            child: const Text('Retry'),
                          ),
                        ],
                      ),
                    ),
                  );
                }

                final data = snapshot.data!;
                final visible = data.take(_pageSize);

                return RefreshIndicator(
                  onRefresh: _refresh,
                  child: ListView(
                    physics: const AlwaysScrollableScrollPhysics(),
                    padding: const EdgeInsets.fromLTRB(16, 0, 16, 24),
                    children: [
                      if (visible.isEmpty)
                        const Padding(
                          padding: EdgeInsets.all(24),
                          child: Text('No matching follow-up tasks.'),
                        ),

                      for (final item in visible) _card(item),
                      if (_page > 0 || data.length > _pageSize)
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            TextButton(
                              onPressed: _page > 0
                                  ? () => _load(_page - 1)
                                  : null,
                              child: const Text('Previous'),
                            ),
                            Text('Page ${_page + 1}'),
                            TextButton(
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