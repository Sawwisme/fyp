import 'dart:async';

import 'package:flutter/material.dart';

import '../services/api_client.dart';
import '../services/appointment_service.dart';
import '../services/pet_service.dart';
import 'emergency_request.dart';

class EmergencyRequestsScreen extends StatefulWidget {
  final AppointmentService service;
  final PetService petService;

  const EmergencyRequestsScreen({
    super.key,
    required this.service,
    required this.petService,
  });

  @override
  State<EmergencyRequestsScreen> createState() =>
      _EmergencyRequestsScreenState();
}

class _EmergencyRequestsScreenState
    extends State<EmergencyRequestsScreen> {
  final List<Map<String, dynamic>> _requests = [];

  bool _loading = false;
  bool _hasMore = true;
  bool _opening = false;
  String? _error;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _load(reset: true);

    _timer = Timer.periodic(const Duration(seconds: 30), (_) {
      if (mounted &&
          !_loading &&
          !_opening &&
          _requests.length <= 20 &&
          ModalRoute.of(context)?.isCurrent == true &&
          WidgetsBinding.instance.lifecycleState ==
              AppLifecycleState.resumed) {
        _load(reset: true);
      }
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _load({bool reset = false}) async {
    if (_loading) return;

    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final page = await widget.service.getMyEmergencyRequests(
        offset: reset ? 0 : _requests.length,
        limit: 20,
      );

      if (!mounted) return;

      setState(() {
        if (reset) _requests.clear();
        _requests.addAll(page);
        _hasMore = page.length == 20;
      });
    } on ApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } catch (_) {
      if (mounted) {
        setState(() {
          _error = 'Could not load your emergency requests.';
        });
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _newRequest() async {
    if (_opening) return;

    setState(() => _opening = true);

    try {
      final created = await Navigator.of(context).push<bool>(
        MaterialPageRoute(
          builder: (_) => EmergencyRequestScreen(
            service: widget.service,
            petService: widget.petService,
          ),
        ),
      );

      if (!mounted) return;

      // Also refresh after leaving an uncertain submission.
      await _load(reset: true);

      if (!mounted || created != true) return;

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Request submitted. Waiting for the clinic to review it.',
          ),
        ),
      );
    } finally {
      if (mounted) setState(() => _opening = false);
    }
  }

  Future<void> _cancelRequest(Map<String, dynamic> item) async {
    if (_loading || _opening) return;

    setState(() => _opening = true);
    var attempted = false;

    try {
      final confirmed = await showDialog<bool>(
        context: context,
        builder: (dialogContext) => AlertDialog(
          title: const Text('Cancel emergency request?'),
          content: Text(
            'Cancel the pending request for ${item['pet_name']} '
                'at ${item['clinic_name']}?',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogContext, false),
              child: const Text('Keep request'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(dialogContext, true),
              child: const Text('Cancel request'),
            ),
          ],
        ),
      );

      if (!mounted || confirmed != true) return;

      attempted = true;

      await widget.service.cancelEmergencyRequest(
        item['emergency_appointment_id'] as int,
      );

      if (!mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Emergency request cancelled.')),
      );
    } on ApiException catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(error.message)),
        );
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'Could not confirm cancellation. '
                  'Refresh to check the latest status.',
            ),
          ),
        );
      }
    } finally {
      if (mounted && attempted) {
        await _load(reset: true);
      }

      if (mounted) {
        setState(() => _opening = false);
      }
    }
  }

  String _statusLabel(String value) {
    switch (value) {
      case 'pending':
        return 'Waiting for clinic review';
      case 'approved':
        return 'Request approved';
      case 'rejected':
        return 'Request declined';
      case 'cancelled':
        return 'Request cancelled';
      default:
        return value;
    }
  }

  Color _statusColor(String value) {
    switch (value) {
      case 'approved':
        return const Color(0xFF2549C7);
      case 'rejected':
        return const Color(0xFFB3261E);
      case 'pending':
        return const Color(0xFF855600);
      default:
        return Colors.grey.shade700;
    }
  }

  Widget _requestCard(Map<String, dynamic> item) {
    final status = item['approval_status'] as String;

    return Card(
      margin: const EdgeInsets.only(bottom: 14),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              item['pet_name'] as String,
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 6),
            Text(item['clinic_name'] as String),
            const SizedBox(height: 12),
            Text(
              _statusLabel(status),
              style: TextStyle(
                color: _statusColor(status),
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 12),
            Text(item['emergency_reason'] as String),

            if (status == 'pending') ...[
              const SizedBox(height: 12),
              const Text(
                'No appointment is confirmed yet. Contact the '
                    'clinic directly for immediate assistance.',
              ),
              const SizedBox(height: 12),
              OutlinedButton(
                onPressed: _loading || _opening
                    ? null
                    : () => _cancelRequest(item),
                child: const Text('Cancel request'),
              ),
            ],

            if (item['rejection_reason'] != null) ...[
              const SizedBox(height: 12),
              Text('Clinic response: ${item['rejection_reason']}'),
            ],

            if (item['appointment_id'] != null) ...[
              const SizedBox(height: 12),
              Text('Appointment #${item['appointment_id']}'),
              const Text(
                'Return to My Appointments to view the assigned '
                    'vet, date and time.',
              ),
            ],
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Emergency requests')),
      body: RefreshIndicator(
        onRefresh: () => _load(reset: true),
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.all(20),
          children: [
            const Text(
              'Submit a request to a registered clinic and '
                  'track its response here.',
            ),
            const SizedBox(height: 16),

            FilledButton.icon(
              onPressed: _loading || _opening ? null : _newRequest,
              icon: const Icon(Icons.add),
              label: const Text('New emergency request'),
            ),
            const SizedBox(height: 20),

            if (_error != null) ...[
              Text(
                _error!,
                style: TextStyle(
                  color: Theme.of(context).colorScheme.error,
                ),
              ),
              TextButton(
                onPressed: _loading
                    ? null
                    : () => _load(reset: _requests.isEmpty),
                child: const Text('Try again'),
              ),
            ],

            ..._requests.map(_requestCard),

            if (!_loading && _error == null && _requests.isEmpty)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 24),
                child: Text(
                  'No emergency requests yet.',
                  textAlign: TextAlign.center,
                ),
              ),

            if (_loading)
              const Padding(
                padding: EdgeInsets.all(20),
                child: Center(child: CircularProgressIndicator()),
              )
            else if (_hasMore && _error == null)
              TextButton(
                onPressed: () => _load(),
                child: const Text('Load more'),
              ),
          ],
        ),
      ),
    );
  }
}