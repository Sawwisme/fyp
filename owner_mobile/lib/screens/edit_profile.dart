import 'package:flutter/material.dart';

import '../services/api_client.dart';
import '../services/profile_service.dart';

class EditProfileScreen extends StatefulWidget {
  final ProfileService service;

  const EditProfileScreen({
    super.key,
    required this.service,
  });

  @override
  State<EditProfileScreen> createState() => _EditProfileScreenState();
}

class _EditProfileScreenState extends State<EditProfileScreen> {
  final _formKey = GlobalKey<FormState>();
  final _name = TextEditingController();
  final _phone = TextEditingController();
  final _address = TextEditingController();

  String? _defaultState;

  static const _states = [
    'Johor', 'Kedah', 'Kelantan', 'Melaka',
    'Negeri Sembilan', 'Pahang', 'Pulau Pinang',
    'Perak', 'Perlis', 'Sabah', 'Sarawak',
    'Selangor', 'Terengganu',
    'W.P. Kuala Lumpur', 'W.P. Labuan', 'W.P. Putrajaya',
  ];

  Map<String, dynamic>? _profile;
  bool _loading = true;
  bool _saving = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadProfile();
  }

  Future<void> _loadProfile() async {
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final profile = await widget.service.getProfile();

      if (!mounted) return;

      final user = profile['user'] as Map<String, dynamic>;
      _name.text = user['full_name'] as String;
      _phone.text = user['phone_number'] as String? ?? '';
      _address.text = profile['default_address'] as String? ?? '';
      final savedState = profile['default_state'];
      _defaultState =
      savedState is String && _states.contains(savedState)
          ? savedState
          : null;

      setState(() => _profile = profile);
    } on ApiException catch (error) {
      if (mounted) {
        setState(() => _error = error.message);
      }
    } catch (_) {
      if (mounted) {
        setState(() => _error = 'Unable to load your profile.');
      }
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  String? _optionalText(TextEditingController controller) {
    final text = controller.text.trim();
    return text.isEmpty ? null : text;
  }

  Future<void> _save() async {
    if (_saving || !_formKey.currentState!.validate()) return;

    setState(() {
      _saving = true;
      _error = null;
    });

    try {
      final profile = await widget.service.updateProfile({
        'full_name': _name.text.trim(),
        'phone_number': _optionalText(_phone),
        'default_address': _optionalText(_address),
        'default_state': _defaultState,
      });

      if (!mounted) return;
      Navigator.of(context).pop(profile);
    } on ApiException catch (error) {
      if (mounted) {
        setState(() => _error = error.message);
      }
    } catch (_) {
      if (mounted) {
        setState(() => _error = 'Unable to save your profile.');
      }
    } finally {
      if (mounted) {
        setState(() => _saving = false);
      }
    }
  }

  @override
  void dispose() {
    _name.dispose();
    _phone.dispose();
    _address.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    Widget body;

    if (_loading) {
      body = const Center(child: CircularProgressIndicator());
    } else if (_profile == null) {
      body = Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(_error ?? 'Unable to load profile.'),
              const SizedBox(height: 16),
              FilledButton(
                onPressed: _loadProfile,
                child: const Text('Retry'),
              ),
            ],
          ),
        ),
      );
    } else {
      final user = _profile!['user'] as Map<String, dynamic>;

      body = Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.all(24),
          children: [
            TextFormField(
              controller: _name,
              enabled: !_saving,
              maxLength: 150,
              decoration: const InputDecoration(
                labelText: 'Full name',
                border: OutlineInputBorder(),
              ),
              validator: (value) {
                if (value == null || value.trim().isEmpty) {
                  return 'Enter your full name';
                }
                return null;
              },
            ),
            const SizedBox(height: 16),
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.email_outlined),
              title: const Text('Email'),
              subtitle: Text(user['email'] as String),
            ),
            const SizedBox(height: 16),
            TextFormField(
              controller: _phone,
              enabled: !_saving,
              maxLength: 20,
              keyboardType: TextInputType.phone,
              decoration: const InputDecoration(
                labelText: 'Phone number',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 16),
            TextFormField(
              controller: _address,
              enabled: !_saving,
              maxLength: 255,
              maxLines: 3,
              decoration: const InputDecoration(
                labelText: 'Address',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 16),
            DropdownButtonFormField<String>(
              key: ValueKey('profile-state-$_defaultState'),
              initialValue: _defaultState ?? '',
              isExpanded: true,
              decoration: const InputDecoration(
                labelText: 'Address state / federal territory',
                border: OutlineInputBorder(),
                helperText: 'Used to pre-fill your delivery destination.',
              ),
              items: [
                const DropdownMenuItem(
                  value: '',
                  child: Text('Select state'),
                ),
                for (final state in _states)
                  DropdownMenuItem(
                    value: state,
                    child: Text(state),
                  ),
              ],
              onChanged: _saving
                  ? null
                  : (value) {
                setState(() {
                  _defaultState =
                  value == null || value.isEmpty
                      ? null
                      : value;
                });
              },
              validator: (value) {
                if (_address.text.trim().isNotEmpty &&
                    (value == null || value.isEmpty)) {
                  return 'Select the state for your address';
                }
                return null;
              },
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
              onPressed: _saving ? null : _save,
              child: Text(_saving ? 'Saving…' : 'Save changes'),
            ),
          ],
        ),
      );
    }

    return PopScope(
      canPop: !_saving,
      child: Scaffold(
        appBar: AppBar(title: const Text('Edit profile')),
        body: body,
      ),
    );
  }
}