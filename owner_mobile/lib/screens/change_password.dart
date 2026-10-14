import 'dart:convert';

import 'package:flutter/material.dart';

import '../services/api_client.dart';
import '../services/auth_service.dart';

class ChangePasswordScreen extends StatefulWidget {
  final AuthService auth;

  const ChangePasswordScreen({
    super.key,
    required this.auth,
  });

  @override
  State<ChangePasswordScreen> createState() =>
      _ChangePasswordScreenState();
}

class _ChangePasswordScreenState extends State<ChangePasswordScreen> {
  final _formKey = GlobalKey<FormState>();
  final _current = TextEditingController();
  final _newPassword = TextEditingController();
  final _confirmation = TextEditingController();

  bool _hideCurrent = true;
  bool _hideNew = true;
  bool _hideConfirmation = true;
  bool _saving = false;
  String? _error;

  Future<void> _save() async {
    if (_saving || !_formKey.currentState!.validate()) return;

    setState(() {
      _saving = true;
      _error = null;
    });

    try {
      await widget.auth.changePassword(
        currentPassword: _current.text,
        newPassword: _newPassword.text,
      );

      if (!mounted) return;
      Navigator.of(context).pop(true);
    } on ApiException catch (error) {
      if (mounted) {
        setState(() => _error = error.message);
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          _error = 'Unable to complete the request. Please try again.';
        });
      }
    } finally {
      if (mounted) {
        setState(() => _saving = false);
      }
    }
  }

  Widget _passwordField({
    required TextEditingController controller,
    required String label,
    required bool hidden,
    required VoidCallback toggle,
    required String? Function(String?) validator,
  }) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 20),
      child: TextFormField(
        controller: controller,
        enabled: !_saving,
        obscureText: hidden,
        autocorrect: false,
        enableSuggestions: false,
        decoration: InputDecoration(
          labelText: label,
          border: const OutlineInputBorder(),
          suffixIcon: IconButton(
            tooltip: hidden ? 'Show password' : 'Hide password',
            onPressed: _saving ? null : toggle,
            icon: Icon(
              hidden ? Icons.visibility : Icons.visibility_off,
            ),
          ),
        ),
        validator: validator,
      ),
    );
  }

  @override
  void dispose() {
    _current.dispose();
    _newPassword.dispose();
    _confirmation.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: !_saving,
      child: Scaffold(
        appBar: AppBar(title: const Text('Change password')),
        body: Form(
          key: _formKey,
          child: ListView(
            padding: const EdgeInsets.all(24),
            children: [
              const Text(
                'After changing your password, you will need to '
                    'log in again on all devices.',
              ),
              const SizedBox(height: 24),
              _passwordField(
                controller: _current,
                label: 'Current password',
                hidden: _hideCurrent,
                toggle: () {
                  setState(() => _hideCurrent = !_hideCurrent);
                },
                validator: (value) {
                  if (value == null || value.isEmpty) {
                    return 'Enter your current password';
                  }
                  if (utf8.encode(value).length > 72) {
                    return 'Password is too long';
                  }
                  return null;
                },
              ),
              _passwordField(
                controller: _newPassword,
                label: 'New password',
                hidden: _hideNew,
                toggle: () {
                  setState(() => _hideNew = !_hideNew);
                },
                validator: (value) {
                  final password = value ?? '';
                  if (password.length < 8) {
                    return 'Use at least 8 characters';
                  }
                  if (utf8.encode(password).length > 72) {
                    return 'Password is too long';
                  }
                  if (password == _current.text) {
                    return 'Choose a different new password';
                  }
                  return null;
                },
              ),
              _passwordField(
                controller: _confirmation,
                label: 'Confirm new password',
                hidden: _hideConfirmation,
                toggle: () {
                  setState(() {
                    _hideConfirmation = !_hideConfirmation;
                  });
                },
                validator: (value) {
                  if (value == null || value.isEmpty) {
                    return 'Confirm your new password';
                  }
                  if (value != _newPassword.text) {
                    return 'Passwords do not match';
                  }
                  return null;
                },
              ),
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
                child: Text(
                  _saving ? 'Saving…' : 'Change password',
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}