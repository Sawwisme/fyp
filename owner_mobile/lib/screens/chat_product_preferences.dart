import 'package:flutter/material.dart';

import '../services/shop_service.dart';

class ChatProductPreferences extends StatefulWidget {
  final ShopService service;

  const ChatProductPreferences({
    super.key,
    required this.service,
  });

  @override
  State<ChatProductPreferences> createState() =>
      _ChatProductPreferencesState();
}

class _ChatProductPreferencesState
    extends State<ChatProductPreferences> {
  static const _states = [
    'Johor', 'Kedah', 'Kelantan', 'Melaka',
    'Negeri Sembilan', 'Pahang', 'Pulau Pinang',
    'Perak', 'Perlis', 'Sabah', 'Sarawak',
    'Selangor', 'Terengganu',
    'W.P. Kuala Lumpur', 'W.P. Labuan', 'W.P. Putrajaya',
  ];

  String? _state;
  String? _fulfilment;
  int? _clinicId;
  List<Map<String, dynamic>> _clinics = [];
  bool _loading = true;
  String? _error;
  int _version = 0;

  @override
  void initState() {
    super.initState();
    _loadClinics();
  }

  Future<void> _loadClinics() async {
    final version = ++_version;
    final state = _state;
    final fulfilment = _fulfilment;

    setState(() {
      _loading = true;
      _clinicId = null;
      _clinics = [];
      _error = null;
    });

    try {
      final clinics = <Map<String, dynamic>>[];

      for (var offset = 0; ; offset += 100) {
        final batch = await widget.service.getClinics(
          state: state,
          fulfilment: fulfilment,
          offset: offset,
          limit: 100,
        );

        if (!mounted || version != _version) return;

        clinics.addAll(batch);
        if (batch.length < 100) break;
      }

      setState(() => _clinics = clinics);
    } catch (_) {
      if (!mounted || version != _version) return;

      setState(() {
        _error = 'Could not load clinics. Please try again.';
      });
    } finally {
      if (mounted && version == _version) {
        setState(() => _loading = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Product preferences'),
      content: SizedBox(
        width: 420,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Products will still be checked against your selected '
                    'pet’s records and safety restrictions.',
              ),
              const SizedBox(height: 18),
              DropdownButtonFormField<String>(
                initialValue: '',
                isExpanded: true,
                decoration: const InputDecoration(
                  labelText: 'Clinic state',
                  border: OutlineInputBorder(),
                ),
                items: [
                  const DropdownMenuItem(
                    value: '',
                    child: Text('All states'),
                  ),
                  for (final state in _states)
                    DropdownMenuItem(
                      value: state,
                      child: Text(state),
                    ),
                ],
                onChanged: (value) {
                  _state =
                  value == null || value.isEmpty ? null : value;
                  _loadClinics();
                },
              ),
              const SizedBox(height: 14),
              DropdownButtonFormField<String>(
                initialValue: '',
                isExpanded: true,
                decoration: const InputDecoration(
                  labelText: 'Fulfilment',
                  border: OutlineInputBorder(),
                ),
                items: const [
                  DropdownMenuItem(
                    value: '',
                    child: Text('Pickup or delivery'),
                  ),
                  DropdownMenuItem(
                    value: 'pickup',
                    child: Text('Clinic pickup'),
                  ),
                  DropdownMenuItem(
                    value: 'delivery',
                    child: Text('Delivery available'),
                  ),
                ],
                onChanged: (value) {
                  _fulfilment =
                  value == null || value.isEmpty ? null : value;
                  _loadClinics();
                },
              ),
              const SizedBox(height: 14),
              if (_loading)
                const LinearProgressIndicator()
              else if (_error != null) ...[
                Text(_error!),
                TextButton(
                  onPressed: _loadClinics,
                  child: const Text('Retry'),
                ),
              ] else ...[
                DropdownButtonFormField<int>(
                  key: ValueKey(_version),
                  initialValue: 0,
                  isExpanded: true,
                  decoration: const InputDecoration(
                    labelText: 'Preferred clinic',
                    border: OutlineInputBorder(),
                  ),
                  items: [
                    const DropdownMenuItem(
                      value: 0,
                      child: Text('Any matching clinic'),
                    ),
                    for (final clinic in _clinics)
                      DropdownMenuItem(
                        value: clinic['clinic_id'] as int,
                        child: Text(
                          '${clinic['clinic_name']}',
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                  ],
                  onChanged: (value) {
                    _clinicId = value == 0 ? null : value;
                  },
                ),
                if (_clinics.isEmpty)
                  const Padding(
                    padding: EdgeInsets.only(top: 10),
                    child: Text(
                      'No clinic shops match these filters. '
                          'Try another state or fulfilment option.',
                    ),
                  ),
              ],
              const SizedBox(height: 14),
              const Text(
                'Delivery availability does not confirm coverage '
                    'for your address. Review fulfilment at checkout.',
                style: TextStyle(fontSize: 12),
              ),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: _loading || _error != null || _clinics.isEmpty
              ? null
              : () => Navigator.pop(context, <String, dynamic>{
            if (_state != null) 'state': _state,
            if (_fulfilment != null)
              'fulfilment': _fulfilment,
            if (_clinicId != null) 'clinic_id': _clinicId,
          }),
          child: const Text('Recommend products'),
        ),
      ],
    );
  }
}