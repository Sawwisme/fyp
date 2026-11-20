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
import 'medical_history.dart';
import '../services/shop_service.dart';
import 'shop.dart';
import '../services/notification_service.dart';
import 'notification_bell.dart';
import '../services/billing_service.dart';
import 'bills.dart';
import '../services/dental_assessment_service.dart';
import 'ai_scan.dart';
import '../services/chatbot_service.dart';
import 'chatbot.dart';
import '../services/followup_service.dart';
import 'followup_care.dart';
import 'appointment_details.dart';

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
  static const _green = Color(0xFF2549C7);

  late final PetService _petService;
  late final DentalAssessmentService _dentalAssessmentService;
  late final AppointmentService _appointmentService;
  late final ShopService _shopService;
  late Map<String, dynamic> _user;
  late Future<Map<String, dynamic>?> _nextAppointmentFuture;
  late Future<List<Map<String, dynamic>>> _followupsFuture;

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
    _dentalAssessmentService = DentalAssessmentService(widget.auth.api);
    _appointmentService = AppointmentService(widget.auth.api);
    _shopService = ShopService(widget.auth.api);
    _nextAppointmentFuture = _fetchNextAppointment();
    _followupsFuture = _fetchOpenFollowups();
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

  bool _openingMedicalHistory = false;

  Future<void> _openMedicalHistory() async {
    if (_openingMedicalHistory || _loggingOut) return;

    setState(() => _openingMedicalHistory = true);

    try {
      final pets = <Map<String, dynamic>>[];
      var offset = 0;

      while (true) {
        final page = await _petService.getPets(
          offset: offset,
          limit: 100,
        );

        if (!mounted) return;

        pets.addAll(page);
        if (page.length < 100) break;

        offset += page.length;
      }

      if (pets.isEmpty) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Register a pet to view medical history.'),
          ),
        );
        return;
      }

      Map<String, dynamic>? selectedPet;

      if (pets.length == 1) {
        selectedPet = pets.first;
      } else {
        selectedPet =
        await showModalBottomSheet<Map<String, dynamic>>(
          context: context,
          showDragHandle: true,
          builder: (sheetContext) => SafeArea(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Padding(
                  padding: const EdgeInsets.all(16),
                  child: Text(
                    'Choose a pet',
                    style: Theme.of(sheetContext).textTheme.titleLarge,
                  ),
                ),
                Flexible(
                  child: ListView.builder(
                    shrinkWrap: true,
                    itemCount: pets.length,
                    itemBuilder: (_, index) {
                      final pet = pets[index];

                      return ListTile(
                        leading: const CircleAvatar(
                          child: Icon(Icons.pets),
                        ),
                        title: Text(pet['pet_name'] as String),
                        subtitle: Text(
                          '${pet['species']} · Pet #${pet['pet_id']}',
                        ),
                        trailing: const Icon(Icons.chevron_right),
                        onTap: () => Navigator.pop(sheetContext, pet),
                      );
                    },
                  ),
                ),
              ],
            ),
          ),
        );
      }

      if (!mounted || selectedPet == null) return;

      final pet = selectedPet;

      await Navigator.of(context).push<void>(
        MaterialPageRoute(
          builder: (_) => MedicalHistoryScreen(
            petId: pet['pet_id'] as int,
            petName: pet['pet_name'] as String,
            service: _petService,
          ),
        ),
      );
    } on ApiException catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(error.message)),
        );
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Could not open medical history. Try again.'),
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _openingMedicalHistory = false);
      }
    }
  }

  Future<Map<String, dynamic>?> _fetchNextAppointment() async {
    final appointments = <Map<String, dynamic>>[];

    for (var offset = 0; ; offset += 100) {
      final page = await _appointmentService.getMyAppointments(
        offset: offset,
        limit: 100,
      );

      appointments.addAll(page);

      if (page.length < 100) break;
    }

    DateTime? appointmentEnd(Map<String, dynamic> item) {
      return DateTime.tryParse(
        '${item['appointment_date']}T${item['end_time']}+08:00',
      );
    }

    final now = DateTime.now().toUtc();

    final upcoming = appointments.where((item) {
      if (!{
        'pending',
        'confirmed',
        'in_progress',
      }.contains(item['status'])) {
        return false;
      }

      final end = appointmentEnd(item);
      return end != null && end.isAfter(now);
    }).toList();

    upcoming.sort((a, b) {
      final startA = DateTime.parse(
        '${a['appointment_date']}T${a['start_time']}+08:00',
      );

      final startB = DateTime.parse(
        '${b['appointment_date']}T${b['start_time']}+08:00',
      );

      return startA.compareTo(startB);
    });

    return upcoming.isEmpty ? null : upcoming.first;
  }

  Future<List<Map<String, dynamic>>> _fetchOpenFollowups() async {
    final service = FollowupService(widget.auth.api);
    final items = <Map<String, dynamic>>[];

    for (var offset = 0; ; offset += 100) {
      final page = await service.getFollowups(
        status: 'pending',
        offset: offset,
        limit: 100,
      );

      items.addAll(page);

      if (page.length < 100) return items;
    }
  }

  Future<void> _refreshDashboard() async {
    setState(() {
      _nextAppointmentFuture = _fetchNextAppointment();
      _followupsFuture = _fetchOpenFollowups();
    });

    // Observe errors here; the individual FutureBuilders display them.
    await Future.wait<void>([
      _loadPet(),
      _nextAppointmentFuture.then<void>(
            (_) {},
        onError: (Object error, StackTrace stack) {},
      ),
      _followupsFuture.then<void>(
            (_) {},
        onError: (Object error, StackTrace stack) {},
      ),
    ]);
  }

  Future<void> _openDashboardAppointment(
      Map<String, dynamic> appointment,
      ) async {
    await Navigator.of(context).push<void>(
      MaterialPageRoute(
        builder: (_) => AppointmentDetailsScreen(
          appointment: appointment,
          service: _appointmentService,
        ),
      ),
    );

    if (mounted) await _refreshDashboard();
  }

  Future<void> _openDashboardFollowups() async {
    await Navigator.of(context).push<void>(
      MaterialPageRoute(
        builder: (_) => FollowupCareScreen(
          service: FollowupService(widget.auth.api),
        ),
      ),
    );

    if (mounted) await _refreshDashboard();
  }

  Future<void> _openDashboardChatbot() async {
    await Navigator.of(context).push<void>(
      MaterialPageRoute(
        builder: (_) => ChatbotScreen(
          service: ChatbotService(widget.auth.api),
        ),
      ),
    );

    if (mounted) await _refreshDashboard();
  }

  String _dashboardDate(dynamic value) {
    final date = DateTime.tryParse('${value ?? ''}');

    if (date == null) return 'Date unavailable';

    return '${date.day.toString().padLeft(2, '0')}/'
        '${date.month.toString().padLeft(2, '0')}/'
        '${date.year}';
  }

  String _dashboardTime(dynamic value) {
    final text = '${value ?? ''}';
    return text.length >= 5 ? text.substring(0, 5) : text;
  }

  Widget _dashboardAction({
    required String label,
    required IconData icon,
    required VoidCallback onTap,
  }) {
    return Material(
      color: Colors.white,
      borderRadius: BorderRadius.circular(16),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: Container(
          constraints: const BoxConstraints(minHeight: 104),
          padding: const EdgeInsets.symmetric(
            horizontal: 10,
            vertical: 16,
          ),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(16),
            border: Border.all(
              color: const Color(0xFFDCE4F2),
            ),
          ),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                padding: const EdgeInsets.all(9),
                decoration: BoxDecoration(
                  color: const Color(0xFFEEF2FF),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(
                  icon,
                  size: 22,
                  color: const Color(0xFF4169D8),
                ),
              ),
              const SizedBox(height: 10),
              Text(
                label,
                textAlign: TextAlign.center,
                style: const TextStyle(
                  color: Color(0xFF263955),
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _nextAppointmentCard() {
    return FutureBuilder<Map<String, dynamic>?>(
      future: _nextAppointmentFuture,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return _panel(
            title: 'Next appointment',
            children: const [LinearProgressIndicator()],
          );
        }

        if (snapshot.hasError) {
          return _panel(
            title: 'Next appointment',
            children: [
              const Text('Could not load your appointment.'),
              TextButton(
                onPressed: () {
                  setState(() {
                    _nextAppointmentFuture = _fetchNextAppointment();
                  });
                },
                child: const Text('Try again'),
              ),
            ],
          );
        }

        final appointment = snapshot.data;

        if (appointment == null) {
          return _panel(
            title: 'Next appointment',
            children: [
              const Text('No upcoming appointments.'),
              const SizedBox(height: 12),
              OutlinedButton.icon(
                onPressed: () => setState(() => _selectedTab = 1),
                icon: const Icon(Icons.calendar_month_outlined),
                label: const Text('Open booking'),
              ),
            ],
          );
        }

        final status = '${appointment['status']}'
            .replaceAll('_', ' ');

        return _panel(
          title: 'Next appointment',
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    '${appointment['pet_name']}',
                    style: const TextStyle(
                      fontSize: 20,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 10,
                    vertical: 6,
                  ),
                  decoration: BoxDecoration(
                    color: const Color(0xFFEEF2FF),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Text(
                    status,
                    style: const TextStyle(
                      color: Color(0xFF2549C7),
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Text('${appointment['clinic_name']}'),
            Text(
              'Vet: ${appointment['veterinarian_name']}',
              style: const TextStyle(color: Color(0xFF63718A)),
            ),
            const SizedBox(height: 14),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: const Color(0xFFF3F5FA),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Row(
                children: [
                  const Icon(
                    Icons.calendar_today_outlined,
                    size: 18,
                    color: Color(0xFF2549C7),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      '${_dashboardDate(appointment['appointment_date'])}'
                          ' · ${_dashboardTime(appointment['start_time'])}'
                          '–${_dashboardTime(appointment['end_time'])} MYT',
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 12),
            TextButton(
              onPressed: () => _openDashboardAppointment(appointment),
              child: const Text('View appointment details'),
            ),
          ],
        );
      },
    );
  }

  Widget _followupDashboardCard() {
    return FutureBuilder<List<Map<String, dynamic>>>(
      future: _followupsFuture,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return _panel(
            title: 'Follow-up care',
            children: const [LinearProgressIndicator()],
          );
        }

        if (snapshot.hasError) {
          return _panel(
            title: 'Follow-up care',
            children: [
              const Text('Could not load your follow-up tasks.'),
              TextButton(
                onPressed: () {
                  setState(() {
                    _followupsFuture = _fetchOpenFollowups();
                  });
                },
                child: const Text('Try again'),
              ),
            ],
          );
        }

        final tasks = snapshot.data ?? [];

        final actionNeeded = tasks.where((task) {
          return {
            'action_needed',
            'update_requested',
            'visit_required',
          }.contains(task['submission_state']);
        }).length;

        final awaitingReview = tasks.where((task) {
          return task['submission_state'] == 'awaiting_review';
        }).length;

        return _panel(
          title: 'Follow-up care',
          children: [
            Text(
              tasks.isEmpty
                  ? 'No open follow-up tasks.'
                  : '${tasks.length} open '
                  '${tasks.length == 1 ? 'task' : 'tasks'}',
              style: const TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w700,
              ),
            ),
            if (actionNeeded > 0) ...[
              const SizedBox(height: 8),
              Text(
                '$actionNeeded require your attention.',
                style: const TextStyle(
                  color: Color(0xFF946200),
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
            if (awaitingReview > 0) ...[
              const SizedBox(height: 6),
              Text('$awaitingReview awaiting vet review.'),
            ],
            const SizedBox(height: 12),
            OutlinedButton.icon(
              onPressed: _openDashboardFollowups,
              icon: const Icon(Icons.monitor_heart_outlined),
              label: const Text('Open follow-up care'),
            ),
          ],
        );
      },
    );
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
        title: 'My pets',
        children: const [
          Center(child: CircularProgressIndicator()),
        ],
      );
    }

    if (_petError != null) {
      return _panel(
        title: 'My pets',
        children: [
          Text(_petError!),
          TextButton(
            onPressed: _loadPet,
            child: const Text('Retry'),
          ),
        ],
      );
    }

    if (_previewPets.isEmpty) {
      return _panel(
        title: 'Welcome to VetDental',
        children: [
          const Text(
            'Register your pet to start managing their dental care.',
          ),
          const SizedBox(height: 16),
          FilledButton.icon(
            onPressed: _registerPet,
            icon: const Icon(Icons.add),
            label: const Text('Add your first pet'),
          ),
        ],
      );
    }

    return _panel(
      title: 'My pets',
      children: [
        for (final pet in _previewPets)
          Container(
            margin: const EdgeInsets.only(bottom: 10),
            decoration: BoxDecoration(
              color: Colors.white,
              border: Border.all(
                color: const Color(0xFFD3DCE5),
              ),
              borderRadius: BorderRadius.circular(14),
            ),
            child: ListTile(
              contentPadding: const EdgeInsets.symmetric(
                horizontal: 14,
                vertical: 6,
              ),
              leading: const CircleAvatar(
                backgroundColor: Color(0xFFE8EDFF),
                child: Icon(Icons.pets, color: _green),
              ),
              title: Text(
                pet['pet_name'] as String,
                style: const TextStyle(
                  fontWeight: FontWeight.w600,
                ),
              ),
              subtitle: Text(
                '${pet['species']}'
                    '${pet['breed'] == null ? '' : ' · ${pet['breed']}'}',
              ),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => _openPetProfile(
                pet['pet_id'] as int,
              ),
            ),
          ),
        TextButton(
          onPressed: _openPets,
          child: const Text('View all pets'),
        ),
        OutlinedButton.icon(
          onPressed: _registerPet,
          icon: const Icon(Icons.add),
          label: const Text('Add pet'),
        ),
      ],
    );
  }

  Widget _homePage() {
    final fullName = '${_user['full_name'] ?? ''}'.trim();
    final firstName = fullName.isEmpty
        ? 'there'
        : fullName.split(RegExp(r'\s+')).first;

    return RefreshIndicator(
      onRefresh: _refreshDashboard,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(20),
        children: [
          Container(
            clipBehavior: Clip.antiAlias,
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [
                  Color(0xFF172E62),
                  Color(0xFF365CD2),
                  Color(0xFF7296EF),
                ],
              ),
              borderRadius: BorderRadius.circular(24),
              boxShadow: [
                BoxShadow(
                  color: const Color(0xFF365CD2).withValues(
                    alpha: 0.18,
                  ),
                  blurRadius: 20,
                  offset: const Offset(0, 8),
                ),
              ],
            ),
            child: Stack(
              children: [
                Positioned(
                  right: -45,
                  top: -55,
                  child: Container(
                    width: 180,
                    height: 180,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      border: Border.all(
                        color: Colors.white.withValues(alpha: 0.12),
                        width: 28,
                      ),
                    ),
                  ),
                ),
                Positioned(
                  right: 30,
                  bottom: -60,
                  child: Container(
                    width: 130,
                    height: 130,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: Colors.white.withValues(alpha: 0.07),
                    ),
                  ),
                ),
                Padding(
                  padding: const EdgeInsets.all(24),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          const Expanded(
                            child: Text(
                              'YOUR PET CARE SPACE',
                              style: TextStyle(
                                color: Color(0xFFE0EDFF),
                                fontSize: 10,
                                fontWeight: FontWeight.w700,
                                letterSpacing: 1.7,
                              ),
                            ),
                          ),
                          Icon(
                            Icons.pets_rounded,
                            size: 26,
                            color: Colors.white.withValues(alpha: 0.8),
                          ),
                        ],
                      ),
                      const SizedBox(height: 20),
                      Text(
                        'Hello, $firstName.',
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 29,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                      const SizedBox(height: 8),
                      const Text(
                        'A little care today.\n'
                            'A healthier smile tomorrow.',
                        style: TextStyle(
                          color: Color(0xFFE0E9FF),
                          fontSize: 14,
                          height: 1.6,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),

          const Text(
            'Quick access',
            style: TextStyle(
              fontSize: 17,
              fontWeight: FontWeight.w700,
              color: Color(0xFF172333),
            ),
          ),
          const SizedBox(height: 12),

          LayoutBuilder(
            builder: (context, constraints) {
              final columns = constraints.maxWidth < 340 ? 2 : 3;
              final width =
                  (constraints.maxWidth - (columns - 1) * 10) / columns;

              final actions = <Widget>[
                _dashboardAction(
                  label: 'Booking',
                  icon: Icons.calendar_month_outlined,
                  onTap: () => setState(() => _selectedTab = 1),
                ),
                _dashboardAction(
                  label: 'AI scan',
                  icon: Icons.camera_alt_outlined,
                  onTap: () => setState(() => _selectedTab = 2),
                ),
                _dashboardAction(
                  label: 'Assistant',
                  icon: Icons.chat_bubble_outline_rounded,
                  onTap: _openDashboardChatbot,
                ),
                _dashboardAction(
                  label: 'Medical history',
                  icon: Icons.medical_information_outlined,
                  onTap: _openMedicalHistory,
                ),
                _dashboardAction(
                  label: 'Bills & receipts',
                  icon: Icons.receipt_long_outlined,
                  onTap: () {
                    Navigator.of(context).push<void>(
                      MaterialPageRoute(
                        builder: (_) => BillsScreen(
                          service: BillingService(widget.auth.api),
                        ),
                      ),
                    );
                  },
                ),
                _dashboardAction(
                  label: 'Shop',
                  icon: Icons.shopping_bag_outlined,
                  onTap: () => setState(() => _selectedTab = 3),
                ),
              ];

              return Wrap(
                spacing: 10,
                runSpacing: 10,
                children: [
                  for (final action in actions)
                    SizedBox(
                      width: width,
                      child: action,
                    ),
                ],
              );
            },
          ),
          const SizedBox(height: 24),

          _nextAppointmentCard(),
          _followupDashboardCard(),
          _petSummary(),

          const SizedBox(height: 8),
        ],
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
              backgroundColor: Color(0xFFE8EDFF),
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
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: const CircleAvatar(
                  backgroundColor: Color(0xFFE8EDFF),
                  child: Icon(
                    Icons.receipt_long_outlined,
                    color: _green,
                  ),
                ),
                title: const Text('Bills & Receipts'),
                trailing: const Icon(Icons.chevron_right),
                onTap: _loggingOut
                    ? null
                    : () {
                  Navigator.of(context).push<void>(
                    MaterialPageRoute(
                      builder: (_) => BillsScreen(
                        service: BillingService(
                          widget.auth.api,
                        ),
                      ),
                    ),
                  );
                },
              ),
              const Divider(),
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
                  backgroundColor: Color(0xFFE8EDFF),
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
                  backgroundColor: Color(0xFFE8EDFF),
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
                            color: const Color(0xFFD3DCE5),
                          ),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: ListTile(
                          leading: const CircleAvatar(
                            backgroundColor: Color(0xFFE8EDFF),
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
        return AiScanPage(
          petService: _petService,
          service: _dentalAssessmentService,
        );
      case 3:
        return ShopScreen(service: _shopService);
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
        backgroundColor: const Color(0xFFEEF1F5),
        appBar: AppBar(
          backgroundColor: const Color(0xFF172333), foregroundColor: Colors.white,
          title: const Text(
            'VetDental',
            style: TextStyle(
              color: Colors.white,
              fontWeight: FontWeight.bold,
            ),
          ),
          actions: [
            IconButton(
              tooltip: 'Dental care assistant',
              onPressed: _loggingOut
                  ? null
                  : () {
                Navigator.of(context).push(
                  MaterialPageRoute(
                    builder: (_) => ChatbotScreen(
                      service: ChatbotService(widget.auth.api),
                    ),
                  ),
                );
              },
              icon: const Icon(Icons.chat_bubble_outline_rounded),
            ),
            OwnerNotificationBell(
              key: ValueKey('notifications-${_user['user_id']}'),
              userId: _user['user_id'] as int,
              service: NotificationService(widget.auth.api),
              enabled: !_loggingOut,
            ),
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
            final returningHome = index == 0 && _selectedTab != 0;

            setState(() => _selectedTab = index);

            if (returningHome) {
              _refreshDashboard();
            }
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