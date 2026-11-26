import 'package:flutter/material.dart';

import '../services/shop_service.dart';
import '../services/profile_service.dart';

class ChatProductPreferences extends StatefulWidget {
  final ShopService service;
  final String language;

  const ChatProductPreferences({
    super.key,
    required this.service,
    this.language = 'en',
  });

  @override
  State<ChatProductPreferences> createState() =>
      _ChatProductPreferencesState();
}

class _ChatProductPreferencesState extends State<ChatProductPreferences> {
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
  String? _deliveryState;
  bool _initializing = true;
  String? _error;
  int _version = 0;

  @override
  void initState() {
    super.initState();
    _loadSavedDestination();
  }

  Future<void> _loadSavedDestination() async {
    try {
      final profile =
      await ProfileService(widget.service.api).getProfile();

      if (!mounted) return;

      final state = profile['default_state'];
      _deliveryState =
      state is String && _states.contains(state) ? state : null;
    } catch (_) {
      // Missing prefill does not prevent manual destination selection.
    }

    if (!mounted) return;
    setState(() => _initializing = false);
    await _loadClinics();
  }

  String _label(String english) {
    const translations = {
      'Product preferences': ['Pilihan produk', '产品偏好'],
      'Clinic state': ['Negeri klinik', '诊所所在州'],
      'All states': ['Semua negeri', '所有州属'],
      'Fulfilment': ['Kaedah penerimaan', '收货方式'],
      'Pickup or delivery': ['Pengambilan atau penghantaran', '自取或配送'],
      'Clinic pickup': ['Pengambilan di klinik', '诊所自取'],
      'Delivery available': ['Penghantaran tersedia', '提供配送'],
      'Deliver to state': ['Negeri destinasi penghantaran', '配送目的地州属'],
      'Select destination': ['Pilih destinasi', '选择配送目的地'],
      'Preferred clinic': ['Klinik pilihan', '首选诊所'],
      'Any matching clinic': ['Mana-mana klinik yang sepadan', '任何符合条件的诊所'],
      'Retry': ['Cuba lagi', '重试'],
      'Cancel': ['Batal', '取消'],
      'Recommend products': ['Cadangkan produk', '推荐产品'],
      'Select your delivery destination state.': [
        'Pilih negeri destinasi penghantaran anda.',
        '请选择配送目的地州属。',
      ],
      'Could not load clinics. Please try again.': [
        'Klinik tidak dapat dimuatkan. Sila cuba lagi.',
        '无法加载诊所，请重试。',
      ],
      'Pre-filled from your profile when available.': [
        'Diisi daripada profil anda jika tersedia.',
        '如个人资料中有记录，将自动填入。',
      ],
      'Products will still be checked against your selected '
          'pet’s records and safety restrictions.': [
        'Produk tetap disemak berdasarkan rekod haiwan yang '
            'dipilih dan sekatan keselamatan.',
        '产品仍会根据所选宠物的记录及安全限制进行筛选。',
      ],
      'No clinic shops match these filters. '
          'Try another state or fulfilment option.': [
        'Tiada kedai klinik sepadan dengan penapis ini. '
            'Cuba negeri atau kaedah penerimaan lain.',
        '没有诊所商店符合这些筛选条件。请尝试其他州属或收货方式。',
      ],
      'For delivery, suggestions are filtered by the selected '
          'destination state. Confirm your full address, '
          'current coverage and charges at checkout.': [
        'Cadangan penghantaran ditapis mengikut negeri destinasi. '
            'Sahkan alamat penuh, liputan dan caj semasa di checkout.',
        '配送建议会按所选目的地州属筛选。'
            '请在结账时确认完整地址、当前配送范围及费用。',
      ],
    };

    final translated = translations[english];
    if (translated == null) return english;
    if (widget.language == 'ms') return translated[0];
    if (widget.language == 'zh') return translated[1];
    return english;
  }

  Future<void> _loadClinics() async {
    final version = ++_version;
    final state = _state;
    final fulfilment = _fulfilment;
    final destination =
    fulfilment == 'delivery' ? _deliveryState : null;

    setState(() {
      _loading = true;
      _clinicId = null;
      _clinics = [];
      _error = null;
    });

    if (fulfilment == 'delivery' && destination == null) {
      setState(() {
        _loading = false;
        _error = _label('Select your delivery destination state.');
      });
      return;
    }

    try {
      final clinics = <Map<String, dynamic>>[];

      for (var offset = 0; ; offset += 100) {
        final batch = await widget.service.getClinics(
          state: state,
          fulfilment: fulfilment,
          offset: offset,
          limit: 100,
          deliveryState: destination,
        );

        if (!mounted || version != _version) return;

        clinics.addAll(batch);
        if (batch.length < 100) break;
      }

      setState(() => _clinics = clinics);
    } catch (_) {
      if (!mounted || version != _version) return;

      setState(() {
        _error = _label('Could not load clinics. Please try again.');
      });
    } finally {
      if (mounted && version == _version) {
        setState(() => _loading = false);
      }
    }
  }

  @override
  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text(_label('Product preferences')),
      content: SizedBox(
        width: 420,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                _label(
                  'Products will still be checked against your selected '
                      'pet’s records and safety restrictions.',
                ),
              ),
              const SizedBox(height: 18),
              DropdownButtonFormField<String>(
                initialValue: '',
                isExpanded: true,
                decoration: InputDecoration(
                  labelText: _label('Clinic state'),
                  border: const OutlineInputBorder(),
                ),
                items: [
                  DropdownMenuItem(
                    value: '',
                    child: Text(_label('All states')),
                  ),
                  for (final state in _states)
                    DropdownMenuItem(
                      value: state,
                      child: Text(state),
                    ),
                ],
                onChanged: _initializing
                    ? null
                    : (value) {
                  _state = value == null || value.isEmpty
                      ? null
                      : value;
                  _loadClinics();
                },
              ),
              const SizedBox(height: 14),
              DropdownButtonFormField<String>(
                initialValue: '',
                isExpanded: true,
                decoration: InputDecoration(
                  labelText: _label('Fulfilment'),
                  border: const OutlineInputBorder(),
                ),
                items: [
                  DropdownMenuItem(
                    value: '',
                    child: Text(_label('Pickup or delivery')),
                  ),
                  DropdownMenuItem(
                    value: 'pickup',
                    child: Text(_label('Clinic pickup')),
                  ),
                  DropdownMenuItem(
                    value: 'delivery',
                    child: Text(_label('Delivery available')),
                  ),
                ],
                onChanged: _initializing
                    ? null
                    : (value) {
                  _fulfilment = value == null || value.isEmpty
                      ? null
                      : value;
                  _loadClinics();
                },
              ),
              const SizedBox(height: 14),
              if (_fulfilment == 'delivery') ...[
                DropdownButtonFormField<String>(
                  key: ValueKey('destination-$_deliveryState'),
                  initialValue: _deliveryState ?? '',
                  isExpanded: true,
                  decoration: InputDecoration(
                    labelText: _label('Deliver to state'),
                    border: const OutlineInputBorder(),
                    helperText: _label(
                      'Pre-filled from your profile when available.',
                    ),
                  ),
                  items: [
                    DropdownMenuItem(
                      value: '',
                      child: Text(_label('Select destination')),
                    ),
                    for (final state in _states)
                      DropdownMenuItem(
                        value: state,
                        child: Text(state),
                      ),
                  ],
                  onChanged: _initializing
                      ? null
                      : (value) {
                    _deliveryState =
                    value == null || value.isEmpty
                        ? null
                        : value;
                    _loadClinics();
                  },
                ),
                const SizedBox(height: 14),
              ],
              if (_loading)
                const LinearProgressIndicator()
              else if (_error != null) ...[
                Text(_error!),
                TextButton(
                  onPressed: _loadClinics,
                  child: Text(_label('Retry')),
                ),
              ] else ...[
                DropdownButtonFormField<int>(
                  key: ValueKey(_version),
                  initialValue: 0,
                  isExpanded: true,
                  decoration: InputDecoration(
                    labelText: _label('Preferred clinic'),
                    border: const OutlineInputBorder(),
                  ),
                  items: [
                    DropdownMenuItem(
                      value: 0,
                      child: Text(_label('Any matching clinic')),
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
                  Padding(
                    padding: const EdgeInsets.only(top: 10),
                    child: Text(
                      _label(
                        'No clinic shops match these filters. '
                            'Try another state or fulfilment option.',
                      ),
                    ),
                  ),
              ],
              const SizedBox(height: 14),
              Text(
                _label(
                  'For delivery, suggestions are filtered by the selected '
                      'destination state. Confirm your full address, '
                      'current coverage and charges at checkout.',
                ),
                style: const TextStyle(fontSize: 12),
              ),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: Text(_label('Cancel')),
        ),
        FilledButton(
          onPressed: _loading || _error != null || _clinics.isEmpty
              ? null
              : () => Navigator.pop(context, <String, dynamic>{
            if (_state != null) 'state': _state,
            if (_fulfilment != null)
              'fulfilment': _fulfilment,
            if (_clinicId != null) 'clinic_id': _clinicId,
            if (_fulfilment == 'delivery' &&
                _deliveryState != null)
              'delivery_state': _deliveryState,
          }),
          child: Text(_label('Recommend products')),
        ),
      ],
    );
  }
}