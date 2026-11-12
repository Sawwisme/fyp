import 'package:flutter/material.dart';

import '../services/dental_assessment_service.dart';

class AssessmentHistoryScreen extends StatefulWidget {
  final DentalAssessmentService service;
  final List<Map<String, dynamic>> pets;
  final int initialPetId;
  final Future<void> Function(Map<String, dynamic>) onOpen;

  const AssessmentHistoryScreen({
    super.key,
    required this.service,
    required this.pets,
    required this.initialPetId,
    required this.onOpen,
  });

  @override
  State<AssessmentHistoryScreen> createState() =>
      _AssessmentHistoryScreenState();
}

class _AssessmentHistoryScreenState
    extends State<AssessmentHistoryScreen> {
  late int _petId;

  List<Map<String, dynamic>> _items = [];
  int _page = 0;

  bool _loading = true;
  bool _opening = false;
  bool _hasMore = false;

  String? _error;

  @override
  void initState() {
    super.initState();
    _petId = widget.initialPetId;
    _load(0);
  }

  Future<void> _load(int page) async {
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final data = await widget.service.getHistory(
        petId: _petId,
        offset: page * 20,
      );

      if (!mounted) return;

      setState(() {
        _items = (data['items'] as List)
            .map(
              (item) => Map<String, dynamic>.from(item as Map),
        )
            .toList();

        _hasMore = data['has_more'] == true;
        _page = page;
      });
    } catch (error) {
      if (mounted) {
        setState(() => _error = error.toString());
      }
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  Future<void> _open(Map<String, dynamic> item) async {
    if (_opening || _loading) return;

    setState(() {
      _opening = true;
      _error = null;
    });

    try {
      await widget.onOpen(item);

      if (mounted) {
        await _load(_page);
      }
    } catch (error) {
      if (mounted) {
        setState(() => _error = error.toString());
      }
    } finally {
      if (mounted) {
        setState(() => _opening = false);
      }
    }
  }

  String _date(dynamic value) {
    final date = DateTime.tryParse('$value');

    if (date == null) return 'Date unavailable';

    final myt = date.toUtc().add(const Duration(hours: 8));

    String two(int value) => value.toString().padLeft(2, '0');

    return '${two(myt.day)}/${two(myt.month)}/${myt.year} · '
        '${two(myt.hour)}:${two(myt.minute)} MYT';
  }

  Widget _card(Map<String, dynamic> item) {
    final status = '${item['status']}';
    final complete = status == 'completed';
    final active = status == 'queued' || status == 'running';

    final colour = complete
        ? const Color(0xFF2549C7)
        : active
        ? const Color(0xFF8A6500)
        : const Color(0xFF687284);

    final findings = (item['findings'] as List? ?? []).join(', ');

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: _opening || _loading ? null : () => _open(item),
        child: Padding(
          padding: const EdgeInsets.all(18),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      'Assessment #${item['assessment_job_id']}',
                      style: const TextStyle(
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
                      color: colour.withValues(alpha: 0.10),
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: Text(
                      complete
                          ? 'Completed'
                          : active
                          ? 'Processing'
                          : status,
                      style: TextStyle(
                        color: colour,
                        fontSize: 12,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Text(
                _date(item['created_at']),
                style: const TextStyle(
                  color: Color(0xFF687284),
                ),
              ),
              const SizedBox(height: 12),
              if (complete) ...[
                Text(
                  'Estimated severity: '
                      '${item['estimated_severity'] ?? 'Unavailable'}',
                ),
                const SizedBox(height: 6),
                Text(
                  findings.isEmpty
                      ? 'No conditions flagged in this photo.'
                      : 'Possible findings: $findings',
                ),
              ] else
                Text(
                  active
                      ? 'Tap to check this assessment’s progress.'
                      : item['message']?.toString() ??
                      'This assessment did not complete.',
                ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Text(
                    complete ? 'View saved result' : 'View details',
                    style: TextStyle(
                      color: colour,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(width: 6),
                  Icon(
                    Icons.arrow_forward,
                    color: colour,
                    size: 16,
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Assessment history'),
      ),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          DropdownButtonFormField<int>(
            initialValue: _petId,
            isExpanded: true,
            decoration: const InputDecoration(
              labelText: 'Your pet',
            ),
            items: [
              for (final pet in widget.pets)
                DropdownMenuItem<int>(
                  value: pet['pet_id'] as int,
                  child: Text(
                    '${pet['pet_name']}',
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
            ],
            onChanged: _loading || _opening
                ? null
                : (value) {
              if (value == null || value == _petId) return;

              setState(() {
                _petId = value;
                _items = [];
                _page = 0;
              });

              _load(0);
            },
          ),
          const SizedBox(height: 20),
          if (_loading || _opening)
            const LinearProgressIndicator(),
          if (_error != null) ...[
            const SizedBox(height: 12),
            Text(
              _error!,
              style: TextStyle(
                color: Theme.of(context).colorScheme.error,
              ),
            ),
            TextButton(
              onPressed: _loading || _opening
                  ? null
                  : () => _load(_page),
              child: const Text('Refresh history'),
            ),
          ],
          if (!_loading && _error == null && _items.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 32),
              child: Text('No assessments for this pet yet.'),
            ),
          const SizedBox(height: 12),
          ..._items.map(_card),
          if (_items.isNotEmpty)
            Row(
              children: [
                OutlinedButton(
                  onPressed: _loading || _opening || _page == 0
                      ? null
                      : () => _load(_page - 1),
                  child: const Text('Previous'),
                ),
                Expanded(
                  child: Text(
                    'Page ${_page + 1}',
                    textAlign: TextAlign.center,
                  ),
                ),
                OutlinedButton(
                  onPressed: _loading || _opening || !_hasMore
                      ? null
                      : () => _load(_page + 1),
                  child: const Text('Next'),
                ),
              ],
            ),
        ],
      ),
    );
  }
}