import 'package:flutter/material.dart';

import '../services/api_client.dart';
import '../services/pet_service.dart';

class PetFormScreen extends StatefulWidget {
  final PetService service;
  final Map<String, dynamic>? initialPet;

  const PetFormScreen(
    {
    super.key,
    required this.service,
    this.initialPet,
    }
  );

  @override
  State<PetFormScreen> createState() => _PetFormScreenState();
}

class _PetFormScreenState extends State<PetFormScreen> {
  final _formKey = GlobalKey<FormState>();

  final _name = TextEditingController();
  final _breed = TextEditingController();
  final _weight = TextEditingController();
  final _colour = TextEditingController();
  final _condition = TextEditingController();
  final _notes = TextEditingController();

  String _species = 'cat';
  String _gender = 'unknown';
  DateTime? _birthDate;
  bool _saving = false;
  String? _error;

  @override
  void initState() {
    super.initState();

    final pet = widget.initialPet;
    if (pet == null) return;

    _name.text = pet['pet_name'] as String;
    _breed.text = pet['breed'] as String? ?? '';
    _weight.text = pet['weight']?.toString() ?? '';
    _colour.text = pet['colour'] as String? ?? '';
    _condition.text = pet['existing_dental_condition'] as String? ?? '';
    _notes.text = pet['notes'] as String? ?? '';

    _species = pet['species'] as String;
    _gender = pet['gender'] as String? ?? 'unknown';

    final birthDate = pet['date_of_birth'] as String?;
    _birthDate = birthDate == null ? null : DateTime.tryParse(birthDate);
  }

  String? _optionalText(TextEditingController controller) {
    final value = controller.text.trim();
    return value.isEmpty ? null : value;
  }

  String _dateText(DateTime value) {
    final month = value.month.toString().padLeft(2, '0');
    final day = value.day.toString().padLeft(2, '0');
    return '${value.year}-$month-$day';
  }

  Future<void> _pickBirthDate() async {
    final today = DateUtils.dateOnly(DateTime.now());

    final selected = await showDatePicker(
      context: context,
      initialDate: _birthDate ?? today,
      firstDate: DateTime(1900),
      lastDate: today,
    );

    if (!mounted || selected == null) return;
    setState(() => _birthDate = selected);
  }

  Future<void> _save() async {
    if (_saving || !_formKey.currentState!.validate()) return;

    setState(() {
      _saving = true;
      _error = null;
    });

    final body = <String, dynamic>{
      'pet_name': _name.text.trim(),
      'species': _species,
      'breed': _optionalText(_breed),
      'gender': _gender,
      'date_of_birth':
          _birthDate == null ? null : _dateText(_birthDate!),
      'weight': _optionalText(_weight),
      'colour': _optionalText(_colour),
      'existing_dental_condition': _optionalText(_condition),
      'notes': _optionalText(_notes),
    };

    try {
      final existingPet = widget.initialPet;

      if (existingPet == null) {
        await widget.service.createPet(body);
      } else {
        await widget.service.updatePet(
          existingPet['pet_id'] as int,
          body,
        );
      }

      if (!mounted) return;
      Navigator.of(context).pop(true);
    } on ApiException catch (error) {
      if (mounted) {
        setState(() => _error = error.message);
      }
    } catch (_) {
      if (mounted) {
        setState(() => _error = 'Unable to save your pet. Please retry.');
      }
    } finally {
      if (mounted) {
        setState(() => _saving = false);
      }
    }
  }

  Widget _textField(
    TextEditingController controller,
    String label,
    int maxLength, {
    int lines = 1,
    bool required = false,
  }) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: TextFormField(
        controller: controller,
        enabled: !_saving,
        maxLength: maxLength,
        maxLines: lines,
        decoration: InputDecoration(
          labelText: label,
          border: const OutlineInputBorder(),
        ),
        validator: (value) {
          if (required && (value == null || value.trim().isEmpty)) {
            return 'Enter $label';
          }
          return null;
        },
      ),
    );
  }

  @override
  void dispose() {
    for (final controller in [
      _name,
      _breed,
      _weight,
      _colour,
      _condition,
      _notes,
    ]) {
      controller.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: !_saving,
      child: Scaffold(
               appBar: AppBar(
          title: Text(
            widget.initialPet == null ? 'Register pet' : 'Edit pet',
          ),
        ),
        body: Form(
          key: _formKey,
          child: ListView(
            padding: const EdgeInsets.all(24),
            children: [
              _textField(_name, 'Pet name', 100, required: true),
              DropdownButtonFormField<String>(
                initialValue: _species,
                decoration: const InputDecoration(
                  labelText: 'Species',
                  border: OutlineInputBorder(),
                ),
                items: const [
                  DropdownMenuItem(value: 'cat', child: Text('Cat')),
                  DropdownMenuItem(value: 'dog', child: Text('Dog')),
                ],
                onChanged: _saving
                    ? null
                    : (value) {
                        if (value != null) {
                          setState(() => _species = value);
                        }
                      },
              ),
              const SizedBox(height: 16),
              _textField(_breed, 'Breed', 100),
              DropdownButtonFormField<String>(
                initialValue: _gender,
                decoration: const InputDecoration(
                  labelText: 'Gender',
                  border: OutlineInputBorder(),
                ),
                items: const [
                  DropdownMenuItem(value: 'male', child: Text('Male')),
                  DropdownMenuItem(value: 'female', child: Text('Female')),
                  DropdownMenuItem(
                    value: 'unknown',
                    child: Text('Unknown'),
                  ),
                ],
                onChanged: _saving
                    ? null
                    : (value) {
                        if (value != null) {
                          setState(() => _gender = value);
                        }
                      },
              ),
              const SizedBox(height: 16),
              ListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text('Date of birth'),
                subtitle: Text(
                  _birthDate == null
                      ? 'Not provided'
                      : _dateText(_birthDate!),
                ),
                onTap: _saving ? null : _pickBirthDate,
                trailing: _birthDate == null
                    ? const Icon(Icons.calendar_today)
                    : IconButton(
                        tooltip: 'Clear date',
                        onPressed: _saving
                            ? null
                            : () => setState(() => _birthDate = null),
                        icon: const Icon(Icons.clear),
                      ),
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _weight,
                enabled: !_saving,
                keyboardType:
                    const TextInputType.numberWithOptions(decimal: true),
                decoration: const InputDecoration(
                  labelText: 'Weight (kg)',
                  border: OutlineInputBorder(),
                ),
                validator: (value) {
                  final text = value?.trim() ?? '';
                  if (text.isEmpty) return null;

                  if (!RegExp(r'^\d{1,3}(\.\d{1,2})?$').hasMatch(text)) {
                    return 'Use up to 3 digits and 2 decimal places';
                  }

                  final weight = double.tryParse(text);
                  if (weight == null || weight <= 0 || weight > 999.99) {
                    return 'Enter a weight between 0.01 and 999.99';
                  }
                  return null;
                },
              ),
              const SizedBox(height: 16),
              _textField(_colour, 'Colour', 50),
              _textField(
                _condition,
                'Existing dental condition',
                10000,
                lines: 3,
              ),
              _textField(_notes, 'Notes', 10000, lines: 3),
              if (_error != null) ...[
                Text(
                  _error!,
                  style: TextStyle(
                    color: Theme.of(context).colorScheme.error,
                  ),
                ),
                const SizedBox(height: 16),
              ],
              FilledButton(
                onPressed: _saving ? null : _save,
                child: Text(_saving ? 'Saving…' : 'Save pet'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}