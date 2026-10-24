import 'package:flutter/material.dart';

import '../services/api_client.dart';
import '../services/appointment_service.dart';
import '../services/pet_service.dart';
import 'clinic_picker.dart';
import 'pet_form.dart';

class EmergencyRequestScreen extends StatefulWidget {
  final AppointmentService service;
  final PetService petService;

  const EmergencyRequestScreen({
    super.key,
    required this.service,
    required this.petService,
  });

  @override
  State<EmergencyRequestScreen> createState() =>
      _EmergencyRequestScreenState();
}

class _EmergencyRequestScreenState
    extends State<EmergencyRequestScreen> {
  final _formKey = GlobalKey<FormState>();
  final _reason = TextEditingController();

  List<Map<String, dynamic>> _pets = [];
  Map<String, dynamic>? _clinic;
  int? _petId;

  bool _loading = true;
  bool _saving = false;
  bool _uncertain = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadPets();
  }

  @override
  void dispose() {
    _reason.dispose();
    super.dispose();
  }

  Future<void> _loadPets() async {
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final pets = <Map<String, dynamic>>[];

      for (var offset = 0; ; offset += 100) {
        final page = await widget.petService.getPets(
          offset: offset,
          limit: 100,
        );

        if (!mounted) return;

        pets.addAll(page);
        if (page.length < 100) break;
      }

      setState(() {
        _pets = pets;

        if (!_pets.any((pet) => pet['pet_id'] == _petId)) {
          _petId = pets.isEmpty ? null : pets.first['pet_id'] as int;
        }
      });
    } on ApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } catch (_) {
      if (mounted) {
        setState(() => _error = 'Could not load your pets.');
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _addPet() async {
    final created = await Navigator.of(context).push<bool>(
      MaterialPageRoute(
        builder: (_) => PetFormScreen(service: widget.petService),
      ),
    );

    if (!mounted || created != true) return;
    await _loadPets();
  }

  Future<void> _chooseClinic() async {
    final clinic =
    await Navigator.of(context).push<Map<String, dynamic>>(
      MaterialPageRoute(
        builder: (_) => ClinicPickerScreen(service: widget.service),
      ),
    );

    if (!mounted || clinic == null) return;

    setState(() => _clinic = clinic);
  }

  Future<void> _submit() async {
    if (_saving || _uncertain || _loading) return;

    if (_clinic == null) {
      setState(() => _error = 'Select a clinic first.');
      return;
    }

    if (_petId == null || !_formKey.currentState!.validate()) return;

    setState(() {
      _saving = true;
      _error = null;
    });

    try {
      await widget.service.submitEmergencyRequest(
        clinicId: _clinic!['clinic_id'] as int,
        petId: _petId!,
        reason: _reason.text,
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
    } catch (_) {
      if (mounted) {
        setState(() {
          _uncertain = true;
          _error = 'Could not confirm submission. '
              'Check your emergency requests before trying again.';
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

    if (_pets.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                _error ?? 'Add a pet before submitting a request.',
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 16),
              if (_error == null)
                FilledButton(
                  onPressed: _addPet,
                  child: const Text('Add pet'),
                ),
              OutlinedButton(
                onPressed: _loadPets,
                child: const Text('Try again'),
              ),
            ],
          ),
        ),
      );
    }

    final disabled = _saving || _uncertain;

    return Form(
      key: _formKey,
      child: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          const Card(
            child: Padding(
              padding: EdgeInsets.all(16),
              child: Text(
                'Submitting a request does not confirm an appointment. '
                    'The clinic must review and accept it. Contact the '
                    'clinic directly for immediate assistance.',
              ),
            ),
          ),
          const SizedBox(height: 20),

          OutlinedButton.icon(
            onPressed: disabled ? null : _chooseClinic,
            icon: const Icon(Icons.local_hospital_outlined),
            label: Text(
              _clinic == null ? 'Select clinic' : 'Change clinic',
            ),
          ),

          if (_clinic != null) ...[
            const SizedBox(height: 12),
            Text(
              _clinic!['clinic_name'] as String,
              style: Theme.of(context).textTheme.titleMedium,
            ),
            Text(
              _clinic!['address'] as String? ??
                  'Address not provided',
            ),
            if (_clinic!['phone_number'] != null)
              Text('Phone: ${_clinic!['phone_number']}'),
          ],

          const SizedBox(height: 24),

          DropdownButtonFormField<int>(
            key: ValueKey(_petId),
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
            onChanged: disabled
                ? null
                : (value) => setState(() => _petId = value),
          ),

          const SizedBox(height: 20),

          TextFormField(
            controller: _reason,
            enabled: !disabled,
            minLines: 4,
            maxLines: 8,
            maxLength: 3000,
            decoration: const InputDecoration(
              labelText: 'Describe what happened',
              hintText: 'Describe your concern and when it started.',
              alignLabelWithHint: true,
              border: OutlineInputBorder(),
            ),
            validator: (value) {
              if ((value ?? '').trim().length < 10) {
                return 'Enter at least 10 characters.';
              }
              return null;
            },
          ),

          if (_error != null) ...[
            const SizedBox(height: 12),
            Text(
              _error!,
              style: TextStyle(
                color: Theme.of(context).colorScheme.error,
              ),
            ),
          ],

          const SizedBox(height: 24),

          FilledButton(
            onPressed: disabled ? null : _submit,
            child: Text(
              _saving ? 'Submitting…' : 'Submit emergency request',
            ),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: !_saving,
      child: Scaffold(
        appBar: AppBar(title: const Text('Emergency request')),
        body: SafeArea(child: _body()),
      ),
    );
  }
}