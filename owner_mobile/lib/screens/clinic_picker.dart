import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'package:url_launcher/url_launcher.dart';

import '../services/api_client.dart';
import '../services/appointment_service.dart';

class ClinicPickerScreen extends StatefulWidget {
  final AppointmentService service;

  const ClinicPickerScreen({
    super.key,
    required this.service,
  });

  @override
  State<ClinicPickerScreen> createState() => _ClinicPickerScreenState();
}

class _ClinicPickerScreenState extends State<ClinicPickerScreen> {
  static const _green = Color(0xFF2549C7);

  List<Map<String, dynamic>> _clinics = [];
  bool _loading = true;
  String? _error;
  String _query = '';
  bool _showMap = true;

  @override
  void initState() {
    super.initState();
    _loadClinics();
  }

  Future<void> _loadClinics() async {
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final collected = <Map<String, dynamic>>[];

      for (var offset = 0; ; offset += 100) {
        final page = await widget.service.getClinics(
          offset: offset,
          limit: 100,
        );

        if (!mounted) return;

        collected.addAll(page);

        if (page.length < 100) break;
      }

      setState(() => _clinics = collected);
    } on ApiException catch (error) {
      if (mounted) {
        setState(() => _error = error.message);
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          _error = 'Unable to load clinics. Please try again.';
        });
      }
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  LatLng? _coordinates(Map<String, dynamic> clinic) {
    final latitude = clinic['latitude'];
    final longitude = clinic['longitude'];

    if (latitude is! num || longitude is! num) return null;

    final lat = latitude.toDouble();
    final lng = longitude.toDouble();

    if (!lat.isFinite || !lng.isFinite ||
        lat < -90 || lat > 90 ||
        lng < -180 || lng > 180) {
      return null;
    }

    return LatLng(lat, lng);
  }

  List<Map<String, dynamic>> get _filtered {
    final query = _query.trim().toLowerCase();

    return _clinics.where((clinic) {
      final text =
      '${clinic['clinic_name']} ${clinic['address'] ?? ''}'
          .toLowerCase();

      return text.contains(query);
    }).toList();
  }

  Future<void> _showClinic(Map<String, dynamic> clinic) async {
    final selected = await showModalBottomSheet<bool>(
      context: context,
      showDragHandle: true,
      isScrollControlled: true,
      builder: (sheetContext) {
        return SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(24, 8, 24, 24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  clinic['clinic_name'] as String,
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                const SizedBox(height: 12),
                Text(
                  clinic['address'] as String? ??
                      'Address not provided',
                ),
                if (clinic['phone_number'] != null) ...[
                  const SizedBox(height: 8),
                  Text(clinic['phone_number'] as String),
                ],
                const SizedBox(height: 16),
                const Text('Select this clinic to continue.'),
                const SizedBox(height: 20),
                FilledButton(
                  onPressed: () {
                    Navigator.of(sheetContext).pop(true);
                  },
                  child: const Text('Select this clinic'),
                ),
              ],
            ),
          ),
        );
      },
    );

    if (!mounted || selected != true) return;

    Navigator.of(context).pop(clinic);
  }

  Widget _map(List<Map<String, dynamic>> clinics) {
    final mapped = clinics
        .where((clinic) => _coordinates(clinic) != null)
        .toList();

    final center = mapped.isNotEmpty
        ? _coordinates(mapped.first)!
        : const LatLng(4.5, 109.5);

    return SizedBox(
      height: 260,
      child: FlutterMap(
        key: ValueKey(_query.trim().toLowerCase()),
        options: MapOptions(
          initialCenter: center,
          initialZoom: mapped.isNotEmpty ? 11 : 5,
          minZoom: 3,
          maxZoom: 18,
        ),
        children: [
          TileLayer(
            urlTemplate:
            'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
            userAgentPackageName: 'com.example.owner_mobile',
          ),
          MarkerLayer(
            markers: mapped.map((clinic) {
              return Marker(
                point: _coordinates(clinic)!,
                width: 48,
                height: 48,
                child: IconButton(
                  tooltip: clinic['clinic_name'] as String,
                  onPressed: () => _showClinic(clinic),
                  icon: const Icon(
                    Icons.location_on,
                    color: _green,
                    size: 40,
                  ),
                ),
              );
            }).toList(),
          ),
          SimpleAttributionWidget(
            source: const Text(
              'OpenStreetMap contributors',
              style: TextStyle(fontSize: 11),
            ),
            onTap: () async {
              final opened = await launchUrl(
                Uri.parse('https://www.openstreetmap.org/copyright'),
              );

              if (!opened && mounted) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text('Could not open attribution link.'),
                  ),
                );
              }
            },
          ),
        ],
      ),
    );
  }

  Widget _content() {
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_error != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(_error!, textAlign: TextAlign.center),
              const SizedBox(height: 16),
              OutlinedButton(
                onPressed: _loadClinics,
                child: const Text('Try again'),
              ),
            ],
          ),
        ),
      );
    }

    final clinics = _filtered;
    final missingPins = clinics
        .where((clinic) => _coordinates(clinic) == null)
        .length;

    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(16),
          child: TextField(
            onChanged: (value) => setState(() => _query = value),
            decoration: const InputDecoration(
              labelText: 'Search clinics',
              hintText: 'Clinic name or address',
              prefixIcon: Icon(Icons.search),
              border: OutlineInputBorder(),
            ),
          ),
        ),
        if (_showMap && clinics.isNotEmpty) _map(clinics),
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
          child: Align(
            alignment: Alignment.centerLeft,
            child: Text(
              '${clinics.length} clinic(s)'
                  '${missingPins > 0 ? ' · $missingPins without map pins' : ''}',
            ),
          ),
        ),
        Expanded(
          child: clinics.isEmpty
              ? const Center(
            child: Text(
              'No matching clinics found.',
              textAlign: TextAlign.center,
            ),
          )
              : ListView.separated(
            padding: const EdgeInsets.only(bottom: 16),
            itemCount: clinics.length,
            separatorBuilder: (_, _) =>
            const Divider(height: 1),
            itemBuilder: (context, index) {
              final clinic = clinics[index];

              return ListTile(
                leading: const CircleAvatar(
                  backgroundColor: Color(0xFFE8EDFF),
                  child: Icon(
                    Icons.local_hospital_outlined,
                    color: _green,
                  ),
                ),
                title: Text(clinic['clinic_name'] as String),
                subtitle: Text(
                  clinic['address'] as String? ??
                      'Address not provided',
                ),
                trailing: const Icon(Icons.chevron_right),
                onTap: () => _showClinic(clinic),
              );
            },
          ),
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Choose a clinic'),
        actions: [
          IconButton(
            tooltip: _showMap ? 'Hide map' : 'Show map',
            onPressed: () {
              setState(() => _showMap = !_showMap);
            },
            icon: Icon(
              _showMap ? Icons.view_list_outlined : Icons.map_outlined,
            ),
          ),
        ],
      ),
      body: SafeArea(child: _content()),
    );
  }
}