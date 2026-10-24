import 'package:flutter/material.dart';

import '../services/api_client.dart';
import '../services/auth_service.dart';
import '../services/pet_service.dart';
import '../services/profile_service.dart';
import 'edit_profile.dart';
import 'pet_detail.dart';
import 'pets.dart';
import 'pet_form.dart';
import 'change_password.dart';
import '../services/appointment_service.dart';
import 'appointments.dart';

class HomeScreen extends StatefulWidget {
  final Map<String, dynamic> user;
  final AuthService auth;
  final VoidCallback onLoggedOut;

  const HomeScreen({
    super.key,
    required this.user,
    required this.auth,
    required this.onLoggedOut,
  });

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  static const _green = Color(0xFF176B32);

  late final PetService _petService;
  late final AppointmentService _appointmentService;
  late Map<String, dynamic> _user;

  int _selectedTab = 0;
  Map<String, dynamic>? _pet;
  List<Map<String, dynamic>> _previewPets = [];
  bool _loadingPets = true;
  bool _loggingOut = false;
  bool _personalInfoExpanded = false;
  String? _petError;

  @override
  void initState() {
    super.initState();
    _user = Map<String, dynamic>.from(widget.user);
    _petService = PetService(widget.auth.api);
    _appointmentService = AppointmentService(widget.auth.api);
    _loadPet();
  }

  Future<void> _loadPet() async {
    if (mounted) {
      setState(() {
        _loadingPets = true;
        _petError = null;
      });
    }

    try {
      final pets = await _petService.getPets(limit: 3);

      if (!mounted) return;

      setState(() {
        _pet = pets.isEmpty ? null : pets.first;
        _previewPets = pets;
      });
    } on ApiException catch (error) {
      if (mounted) {
        setState(() => _petError = error.message);
      }
    } catch (_) {
      if (mounted) {
        setState(() => _petError = 'Unable to load your pet. Please retry.');
      }
    } finally {
      if (mounted) {
        setState(() => _loadingPets = false);
      }
    }
  }

  Future<void> _openPets() async {
    await Navigator.of(context).push<void>(
      MaterialPageRoute(
        builder: (_) => PetsScreen(service: _petService),
      ),
    );

    if (!mounted) return;
    await _loadPet();
  }

  Future<void> _openPetProfile([int? petId]) async {
    final id = petId ?? (_pet?['pet_id'] as int?);
    if (id == null) return;

    await Navigator.of(context).push<void>(
      MaterialPageRoute(
        builder: (_) => PetDetailScreen(
          petId: id,
          service: _petService,
        ),
      ),
    );

    if (!mounted) return;
    await _loadPet();
  }

  Future<void> _registerPet() async {
    final created = await Navigator.of(context).push<bool>(
      MaterialPageRoute(
        builder: (_) => PetFormScreen(service: _petService),
      ),
    );

    if (!mounted || created != true) return;
    await _loadPet();
  }

  Future<void> _logout() async {
    if (_loggingOut) return;
    setState(() => _loggingOut = true);

    try {
      await widget.auth.logout();

      if (!mounted) return;
      widget.onLoggedOut();
    } catch (_) {
      if (!mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Unable to log out. Please try again.'),
        ),
      );
    } finally {
      if (mounted) {
        setState(() => _loggingOut = false);
      }
    }
  }

  Widget _panel({
    required String title,
    required List<Widget> children,
    Color color = Colors.white,
  }) {
    return Card(
      color: color,
      margin: const EdgeInsets.only(bottom: 16),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(18),
      ),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              title,
              style: const TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 16),
            ...children,
          ],
        ),
      ),
    );
  }

  Widget _petSummary() {
    if (_loadingPets) {
      return _panel(
        title: 'Your pet',
        children: const [
          Center(child: CircularProgressIndicator()),
        ],
      );
    }

    if (_petError != null) {
      return _panel(
        title: 'Your pet',
        children: [
          Text(_petError!),
          TextButton(
            onPressed: _loadPet,
            child: const Text('Retry'),
          ),
        ],
      );
    }

    final pet = _pet;

    if (pet == null) {
      return _panel(
        title: 'Welcome to VetDental',
        children: [
          const Text(
            'Register your pet to start managing their dental care.',
          ),
          const SizedBox(height: 16),
          FilledButton.icon(
            onPressed: _openPets,
            icon: const Icon(Icons.add),
            label: const Text('Add your first pet'),
          ),
        ],
      );
    }

    return _panel(
      title: pet['pet_name'] as String,
      children: [
        Row(
          children: [
            const CircleAvatar(
              radius: 28,
              backgroundColor: Color(0xFFE7F2E9),
              child: Icon(Icons.pets, color: _green, size: 30),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Text(
                '${pet['species']}'
                    '${pet['breed'] == null ? '' : ' • ${pet['breed']}'}',
              ),
            ),
          ],
        ),
        const SizedBox(height: 16),
        OutlinedButton.icon(
          onPressed: _openPetProfile,
          icon: const Icon(Icons.pets_outlined),
          label: const Text('View pet profile'),
        ),
        TextButton(
          onPressed: _openPets,
          child: const Text('Manage all my pets'),
        ),
      ],
    );
  }

  Widget _homePage() {
    return RefreshIndicator(
      onRefresh: _loadPet,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(20),
        children: [
          Text(
            'Hello, ${_user['full_name']}',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 6),
          const Text('Care for your pet’s smile.'),
          const SizedBox(height: 20),
          _petSummary(),
          _panel(
            title: 'AI Dental Check',
            color: const Color(0xFFE2F2FC),
            children: [
              const Text(
                'Dental image assessments will be available here soon.',
              ),
              const SizedBox(height: 12),
              OutlinedButton.icon(
                onPressed: () => setState(() => _selectedTab = 2),
                icon: const Icon(Icons.camera_alt_outlined),
                label: const Text('Explore dental scanning'),
              ),
            ],
          ),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              ActionChip(
                avatar: const Icon(Icons.pets, size: 18),
                label: const Text('My pets'),
                onPressed: _openPets,
              ),
              ActionChip(
                avatar: const Icon(Icons.calendar_month, size: 18),
                label: const Text('Booking'),
                onPressed: () => setState(() => _selectedTab = 1),
              ),
              ActionChip(
                avatar: const Icon(Icons.person_outline, size: 18),
                label: const Text('My profile'),
                onPressed: () => setState(() => _selectedTab = 4),
              ),
            ],
          ),
          const SizedBox(height: 20),
          _panel(
            title: 'Upcoming appointment',
            children: const [
              Text(
                'Your appointments will appear here when booking '
                    'becomes available.',
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _comingSoon(IconData icon, String title, String message) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(28),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 64, color: _green),
            const SizedBox(height: 20),
            Text(
              title,
              style: Theme.of(context).textTheme.headlineSmall,
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 12),
            Text(message, textAlign: TextAlign.center),
          ],
        ),
      ),
    );
  }

  Future<void> _editProfile() async {
    final result = await Navigator.of(context)
        .push<Map<String, dynamic>>(
      MaterialPageRoute(
        builder: (_) => EditProfileScreen(
          service: ProfileService(widget.auth.api),
        ),
      ),
    );

    if (!mounted || result == null) return;

    setState(() {
      _user = Map<String, dynamic>.from(
        result['user'] as Map<String, dynamic>,
      );
    });

    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Profile updated.')),
    );
  }

  Future<void> _openChangePassword() async {
    final changed = await Navigator.of(context).push<bool>(
      MaterialPageRoute(
        builder: (_) => ChangePasswordScreen(auth: widget.auth),
      ),
    );

    if (!mounted || changed != true) return;

    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('Password changed. Please log in again.'),
      ),
    );

    await _logout();
  }

  Widget _profilePage() {
    return RefreshIndicator(
      onRefresh: _loadPet,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(20),
        children: [
          const Center(
            child: CircleAvatar(
              radius: 36,
              backgroundColor: Color(0xFFE7F2E9),
              child: Icon(
                Icons.person_outline,
                size: 40,
                color: _green,
              ),
            ),
          ),
          const SizedBox(height: 12),
          Text(
            _user['full_name'] as String,
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 12),
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.email_outlined, size: 18),
              const SizedBox(width: 8),
              Flexible(
                child: Text(_user['email'] as String),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.phone_outlined, size: 18),
              const SizedBox(width: 8),
              Flexible(
                child: Text(
                  _user['phone_number'] as String? ??
                      'Phone not provided',
                ),
              ),
            ],
          ),
          const SizedBox(height: 24),
          OutlinedButton.icon(
            onPressed: _loggingOut ? null : _editProfile,
            icon: const Icon(Icons.edit_outlined),
            label: const Text('Edit profile'),
          ),
          const SizedBox(height: 20),
          _panel(
            title: 'Account',
            children: [
              ExpansionTile(
                tilePadding: EdgeInsets.zero,
                shape: const Border(),
                collapsedShape: const Border(),
                initiallyExpanded: _personalInfoExpanded,
                trailing: Icon(
                  _personalInfoExpanded
                      ? Icons.expand_more
                      : Icons.chevron_right,
                ),
                onExpansionChanged: (expanded) {
                  setState(() => _personalInfoExpanded = expanded);
                },
                leading: const CircleAvatar(
                  backgroundColor: Color(0xFFE7F2E9),
                  child: Icon(
                    Icons.badge_outlined,
                    color: _green,
                  ),
                ),
                title: const Text('Personal information'),
                children: [
                  ListTile(
                    title: const Text('Full name'),
                    subtitle: Text(_user['full_name'] as String),
                  ),
                  ListTile(
                    title: const Text('Email'),
                    subtitle: Text(_user['email'] as String),
                  ),
                  ListTile(
                    title: const Text('Phone'),
                    subtitle: Text(
                      _user['phone_number'] as String? ?? 'Not provided',
                    ),
                  ),
                ],
              ),
              const Divider(),
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: const CircleAvatar(
                  backgroundColor: Color(0xFFE7F2E9),
                  child: Icon(
                    Icons.lock_outline,
                    color: _green,
                  ),
                ),
                title: const Text('Change password'),
                trailing: const Icon(Icons.chevron_right),
                onTap: _loggingOut ? null : _openChangePassword,
              ),
            ],
          ),
          _panel(
            title: 'My Pets',
            children: [
              if (_loadingPets)
                const Padding(
                  padding: EdgeInsets.all(16),
                  child: Center(child: CircularProgressIndicator()),
                )
              else if (_petError != null) ...[
                Text(_petError!),
                TextButton(
                  onPressed: _loadPet,
                  child: const Text('Retry'),
                ),
              ]
              else if (_previewPets.isEmpty)
                  const Padding(
                    padding: EdgeInsets.only(bottom: 16),
                    child: Text('No pets registered yet.'),
                  )
                else ...[
                    ..._previewPets.map(
                          (pet) => Container(
                        margin: const EdgeInsets.only(bottom: 12),
                        decoration: BoxDecoration(
                          border: Border.all(
                            color: const Color(0xFFD5E3D6),
                          ),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: ListTile(
                          leading: const CircleAvatar(
                            backgroundColor: Color(0xFFE7F2E9),
                            child: Icon(Icons.pets, color: _green),
                          ),
                          title: Text(
                            pet['pet_name'] as String,
                            style: const TextStyle(
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                          subtitle: Text(
                            '${pet['species']}'
                                '${pet['breed'] == null ? '' : ', ${pet['breed']}'}',
                          ),
                          trailing: const Icon(Icons.chevron_right),
                          onTap: _loggingOut
                              ? null
                              : () => _openPetProfile(
                            pet['pet_id'] as int,
                          ),
                        ),
                      ),
                    ),
                    TextButton(
                      onPressed: _loggingOut ? null : _openPets,
                      child: const Text('View all pets'),
                    ),
                  ],
              const SizedBox(height: 8),
              OutlinedButton.icon(
                onPressed: _loggingOut || _loadingPets
                    ? null
                    : _registerPet,
                icon: const Icon(Icons.add),
                label: const Text('Register new pet'),
              ),
            ],
          ),
          OutlinedButton.icon(
            onPressed: _loggingOut ? null : _logout,
            style: OutlinedButton.styleFrom(
              foregroundColor: Colors.red.shade700,
              side: BorderSide(color: Colors.red.shade700),
              padding: const EdgeInsets.symmetric(vertical: 16),
            ),
            icon: const Icon(Icons.logout),
            label: Text(_loggingOut ? 'Logging out…' : 'Log out'),
          ),
          const SizedBox(height: 12),
        ],
      ),
    );
  }

  Widget _currentPage() {
    switch (_selectedTab) {
      case 1:
        return AppointmentsPage(
          service: _appointmentService,
          petService: _petService,
        );
      case 2:
        return _comingSoon(
          Icons.camera_alt_outlined,
          'AI dental scan',
          'Upload and review dental images here when scanning '
              'becomes available.',
        );
      case 3:
        return _comingSoon(
          Icons.shopping_bag_outlined,
          'Dental care shop',
          'Pet dental care products will be available here soon.',
        );
      case 4:
        return _profilePage();
      default:
        return _homePage();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Theme(
      data: Theme.of(context).copyWith(
        colorScheme: ColorScheme.fromSeed(seedColor: _green),
      ),
      child: Scaffold(
        backgroundColor: const Color(0xFFF5F7F5),
        appBar: AppBar(
          backgroundColor: const Color(0xFFF5F7F5),
          title: const Text(
            'VetDental',
            style: TextStyle(
              color: _green,
              fontWeight: FontWeight.bold,
            ),
          ),
          actions: [
            IconButton(
              onPressed: () => setState(() => _selectedTab = 4),
              icon: const Icon(Icons.account_circle_outlined),
              tooltip: 'My profile',
            ),
          ],
        ),
        body: _currentPage(),
        bottomNavigationBar: NavigationBar(
          selectedIndex: _selectedTab,
          onDestinationSelected: (index) {
            setState(() => _selectedTab = index);
          },
          destinations: const [
            NavigationDestination(
              icon: Icon(Icons.home_outlined),
              selectedIcon: Icon(Icons.home),
              label: 'Home',
            ),
            NavigationDestination(
              icon: Icon(Icons.calendar_month),
              label: 'Booking',
            ),
            NavigationDestination(
              icon: Icon(Icons.camera_alt_outlined),
              label: 'AI Scan',
            ),
            NavigationDestination(
              icon: Icon(Icons.shopping_bag_outlined),
              label: 'Shop',
            ),
            NavigationDestination(
              icon: Icon(Icons.person_outline),
              label: 'Profile',
            ),
          ],
        ),
      ),
    );
  }
}