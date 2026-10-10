import 'package:flutter/material.dart';

import '../services/api_client.dart';
import '../services/pet_service.dart';

class PetsScreen extends StatefulWidget {
  final PetService service;

  const PetsScreen({
    super.key,
    required this.service,
  });

  @override
  State<PetsScreen> createState() => _PetsScreenState();
}

class _PetsScreenState extends State<PetsScreen> {
  static const _pageSize = 20;

  final List<Map<String, dynamic>> _pets = [];
  bool _loading = false;
  bool _hasMore = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadPets(reset: true);
  }

  Future<void> _loadPets({bool reset = false}) async {
    if (_loading) return;

    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final pets = await widget.service.getPets(
        offset: reset ? 0 : _pets.length,
        limit: _pageSize,
      );

      if (!mounted) return;

      setState(() {
        if (reset) _pets.clear();
        _pets.addAll(pets);
        _hasMore = pets.length == _pageSize;
      });
    } on ApiException catch (error) {
      if (mounted) {
        setState(() => _error = error.message);
      }
    } catch (_) {
      if (mounted) {
        setState(() => _error = 'Unable to load pets. Please try again.');
      }
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('My pets'),
        actions: [
          IconButton(
            onPressed: _loading ? null : () => _loadPets(reset: true),
            icon: const Icon(Icons.refresh),
            tooltip: 'Refresh pets',
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () => _loadPets(reset: true),
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.all(16),
          children: [
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
                    : () => _loadPets(reset: _pets.isEmpty),
                child: const Text('Retry'),
              ),
            ],
            if (_pets.isEmpty && !_loading && _error == null)
              const Padding(
                padding: EdgeInsets.all(24),
                child: Text(
                  'You have no pets registered yet.',
                  textAlign: TextAlign.center,
                ),
              ),
            ..._pets.map(
              (pet) => Card(
                child: ListTile(
                  leading: const Icon(Icons.pets),
                  title: Text(pet['pet_name'] as String),
                  subtitle: Text(
                    '${pet['species']}'
                    '${pet['breed'] == null ? '' : ' • ${pet['breed']}'}',
                  ),
                ),
              ),
            ),
            if (_loading)
              const Padding(
                padding: EdgeInsets.all(24),
                child: Center(child: CircularProgressIndicator()),
              ),
            if (!_loading &&
                _hasMore &&
                _pets.isNotEmpty &&
                _error == null)
              TextButton(
                onPressed: () => _loadPets(),
                child: const Text('Load more'),
              ),
          ],
        ),
      ),
    );
  }
}