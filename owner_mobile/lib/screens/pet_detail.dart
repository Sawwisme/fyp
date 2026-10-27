import 'package:flutter/material.dart';

import '../services/api_client.dart';
import '../services/pet_service.dart';
import 'pet_form.dart';
import 'medical_history.dart';


class PetDetailScreen extends StatefulWidget {
  final int petId;
  final PetService service;

  const PetDetailScreen({
    super.key,
    required this.petId,
    required this.service,
  });

  @override
  State<PetDetailScreen> createState() => _PetDetailScreenState();
}

class _PetDetailScreenState extends State<PetDetailScreen> {
  late Future<Map<String, dynamic>> _petFuture;

  @override
  void initState() {
    super.initState();
    _petFuture = widget.service.getPet(widget.petId);
  }

  void _reload() {
    setState(() {
      _petFuture = widget.service.getPet(widget.petId);
    });
  }

  Future<void> _editPet(Map<String, dynamic> pet) async {
    final saved = await Navigator.of(context).push<bool>(
      MaterialPageRoute(
        builder: (_) => PetFormScreen(
          service: widget.service,
          initialPet: pet,
        ),
      ),
    );

    if (!mounted || saved != true) return;
    _reload();
  }

  Widget _detail(String label, dynamic value, {String suffix = ''}) {
    final text = value?.toString().trim();

    return Card(
      child: ListTile(
        title: Text(label),
        subtitle: Text(
          text == null || text.isEmpty
              ? 'Not provided'
              : '$text$suffix',
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Pet profile')),
      body: FutureBuilder<Map<String, dynamic>>(
        future: _petFuture,
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }

          if (snapshot.hasError) {
            final error = snapshot.error;
            final message = error is ApiException
                ? error.message
                : 'Unable to load your pet. Please retry.';

            return Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(message, textAlign: TextAlign.center),
                    const SizedBox(height: 16),
                    FilledButton(
                      onPressed: _reload,
                      child: const Text('Retry'),
                    ),
                  ],
                ),
              ),
            );
          }

          final pet = snapshot.data!;

          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              const Icon(Icons.pets, size: 64),
              const SizedBox(height: 16),
              Text(
                pet['pet_name'] as String,
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.headlineMedium,
              ),
              const SizedBox(height: 24),
              _detail('Species', pet['species']),
              _detail('Breed', pet['breed']),
              _detail('Gender', pet['gender']),
              _detail('Date of birth', pet['date_of_birth']),
              _detail('Weight', pet['weight'], suffix: ' kg'),
              _detail('Colour', pet['colour']),
              _detail(
                'Existing dental condition',
                pet['existing_dental_condition'],
              ),
              _detail('Notes', pet['notes']),
              OutlinedButton.icon(
                onPressed: () {
                  Navigator.of(context).push(
                    MaterialPageRoute(
                      builder: (_) => MedicalHistoryScreen(
                        petId: widget.petId,
                        petName: pet['pet_name'] as String,
                        service: widget.service,
                      ),
                    ),
                  );
                },
                icon: const Icon(Icons.medical_information_outlined),
                label: const Text('Medical History'),
              ),
              const SizedBox(height: 12),
            const SizedBox(height: 16),
              FilledButton.icon(
                onPressed: () => _editPet(pet),
                icon: const Icon(Icons.edit),
                label: const Text('Edit pet'),
              ),
            ],
          );
        },
      ),
    );
  }
}