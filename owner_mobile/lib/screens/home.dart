import 'package:flutter/material.dart';

import '../services/auth_service.dart';
import '../services/pet_service.dart';
import 'pets.dart';

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
  bool _loggingOut = false;

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

    void _openPets() {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => PetsScreen(
          service: PetService(widget.auth.api),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('My account'),
        actions: [
          TextButton(
            onPressed: _loggingOut ? null : _logout,
            child: Text(_loggingOut ? 'Logging out…' : 'Log out'),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(24),
        children: [
          Text(
            'Hello, ${widget.user['full_name']}',
            style: Theme.of(context).textTheme.headlineSmall,
          ),
          const SizedBox(height: 24),
          Card(
            child: ListTile(
              leading: const Icon(Icons.email_outlined),
              title: const Text('Email'),
              subtitle: Text(widget.user['email'] as String),
            ),
          ),
          Card(
            child: ListTile(
              leading: const Icon(Icons.phone_outlined),
              title: const Text('Phone'),
              subtitle: Text(
                widget.user['phone_number'] as String? ?? 'Not provided',
              ),
            ),
          ),
          Card(
            child: ListTile(
              leading: const Icon(Icons.pets),
              title: const Text('My pets'),
              subtitle: const Text('View your registered pets'),
              trailing: const Icon(Icons.chevron_right),
              onTap: _loggingOut ? null : _openPets,
            ),
          ),
        ],
      ),
    );
  }
}