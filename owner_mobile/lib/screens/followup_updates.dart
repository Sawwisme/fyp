import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import '../services/api_client.dart';
import '../services/followup_service.dart';

class FollowupUpdatesScreen extends StatefulWidget {
  final Map<String, dynamic> followup;
  final FollowupService service;

  const FollowupUpdatesScreen({
    super.key,
    required this.followup,
    required this.service,
  });

  @override
  State<FollowupUpdatesScreen> createState() =>
      _FollowupUpdatesScreenState();
}

class _FollowupUpdatesScreenState extends State<FollowupUpdatesScreen> {
  final _comment = TextEditingController();
  final _picker = ImagePicker();
  final List<Uint8List> _photos = [];
  final Map<int, Future<Uint8List>> _photoRequests = {};

  late Future<List<Map<String, dynamic>>> _history;
  bool _picking = false;
  bool _submitting = false;
  bool _blocked = false;
  String? _message;
  int _page = 0;
  bool _canSubmit = false;
  bool _checkingState = true;
  String _submissionState = '';
  String? _stateError;
  int _stateVersion = 0;

  int get _followupId => widget.followup['followup_care_id'] as int;
  bool get _photosRequired => widget.followup['photos_required'] == true;

  @override
  void initState() {
    super.initState();
    _history = _fetch(0);
    _refreshSubmissionState();
  }

  @override
  void dispose() {
    _comment.dispose();
    super.dispose();
  }

  Future<List<Map<String, dynamic>>> _fetch(int page) {
    return widget.service.getSubmissions(
      _followupId,
      offset: page * 10,
      limit: 11,
    );
  }

  void _loadHistory(int page) {
    setState(() {
      _page = page;
      _history = _fetch(page);
    });

    _refreshSubmissionState();
  }

  String _text(dynamic value) {
    final text = value?.toString().trim();
    return text == null || text.isEmpty ? 'Not recorded' : text;
  }

  String _timestamp(dynamic value) {
    if (value == null) return 'Not recorded';

    var text = value.toString();
    if (!RegExp(
      r'(Z|[+-]\d{2}:\d{2})$',
      caseSensitive: false,
    ).hasMatch(text)) {
      text = '${text}Z';
    }

    final parsed = DateTime.tryParse(text);
    if (parsed == null) return 'Not recorded';

    final date = parsed.toUtc().add(const Duration(hours: 8));
    String two(int value) => value.toString().padLeft(2, '0');

    return '${two(date.day)}/${two(date.month)}/${date.year} '
        '${two(date.hour)}:${two(date.minute)} MYT';
  }

  Future<void> _pick(ImageSource source) async {
    if (_picking || _submitting || _photos.length >= 4) return;

    setState(() {
      _picking = true;
      _message = null;
    });

    try {
      final photo = await _picker.pickImage(
        source: source,
        maxWidth: 1800,
        maxHeight: 1800,
        imageQuality: 85,
        requestFullMetadata: false,
      );

      if (photo == null) return;

      if (await photo.length() > 8 * 1024 * 1024) {
        throw const ApiException('Choose a photo smaller than 8 MB.');
      }

      final bytes = await photo.readAsBytes();

      if (!mounted) return;

      setState(() {
        _photos.add(bytes);
      });
    } catch (error) {
      if (!mounted) return;

      setState(() {
        _message = error is ApiException
            ? error.message
            : 'Unable to select a photo. Check camera/gallery access.';
      });
    } finally {
      if (mounted) {
        setState(() => _picking = false);
      }
    }
  }

  Future<void> _submit() async {
    if (_submitting ||
        _picking ||
        _blocked ||
        _checkingState ||
        !_canSubmit) {
      return;
    }

    if (_photosRequired && _photos.isEmpty) {
      setState(() => _message = 'Your vet requires at least one photo.');
      return;
    }

    if (_photos.isEmpty && _comment.text.trim().isEmpty) {
      setState(() => _message = 'Add a photo or a progress comment.');
      return;
    }

    setState(() {
      _submitting = true;
      _message = null;
    });

    try {
      await widget.service.submitUpdate(
        _followupId,
        comment: _comment.text,
        photos: List<Uint8List>.of(_photos),
      );

      if (!mounted) return;

      _comment.clear();

      setState(() {
        _photos.clear();
        _page = 0;
        _history = _fetch(0);
        _message = 'Update submitted. Your vet will review it.';
      });
    } catch (error) {
      if (!mounted) return;

      final canCorrectInput = error is ApiException &&
          [400, 413, 422].contains(error.statusCode);

      setState(() {
        _blocked = !canCorrectInput;
        _message = error is ApiException
            ? error.message
            : 'Unable to confirm the submission.';

        if (_blocked) {
          _message = '$_message Check history below before reopening '
              'this screen to try again.';
        }

        _page = 0;
        _history = _fetch(0);
      });

      await showDialog<void>(
        context: context,
        builder: (dialogContext) => AlertDialog(
          icon: Icon(
            canCorrectInput
                ? Icons.add_photo_alternate_outlined
                : Icons.cloud_off_outlined,
            color: const Color(0xFF2549C7),
            size: 36,
          ),
          title: Text(
            canCorrectInput
                ? 'Please check your update'
                : 'Submission not confirmed',
          ),
          content: SingleChildScrollView(
            child: Text(
              _message ?? 'Please try again later.',
              style: const TextStyle(height: 1.6),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () =>
                  Navigator.of(dialogContext).pop(),
              child: Text(
                canCorrectInput ? 'Edit update' : 'OK',
              ),
            ),
          ],
        ),
      );
    } finally {
      if (mounted) {
        await _refreshSubmissionState();
        }

        if (mounted) {
        setState(() => _submitting = false);
        }
      }
  }

Future<void> _refreshSubmissionState() async {
  final request = ++_stateVersion;

  setState(() {
    _checkingState = true;
    _canSubmit = false;
    _stateError = null;
  });

  try {
    final data = await widget.service.getSubmissionState(
      _followupId,
    );

    if (!mounted || request != _stateVersion) return;

    setState(() {
      _canSubmit = data['can_submit'] as bool;
      _submissionState = data['submission_state'] as String;
    });
  } catch (error) {
    if (!mounted || request != _stateVersion) return;

    setState(() {
      _canSubmit = false;
      _stateError = error is ApiException
          ? error.message
          : 'Could not check follow-up status.';
    });
  } finally {
    if (mounted && request == _stateVersion) {
      setState(() => _checkingState = false);
    }
  }
}

String get _submissionStatusMessage {
  switch (_submissionState) {
    case 'awaiting_review':
      return 'Your update is awaiting vet review. '
          'You can submit again if your vet requests another update.';
    case 'reviewed':
      return 'Your vet has reviewed your update. '
          'No additional submission has been requested.';
    case 'completed':
      return 'This follow-up is completed. '
          'Your updates and vet feedback remain available below.';
    case 'cancelled':
      return 'This follow-up is cancelled. '
          'Previous updates remain available below.';
    case 'visit_required':
      return 'Your vet requires an in-clinic review. '
          'Check the feedback below and arrange your review appointment.';
    default:
      return 'Please refresh to check the latest follow-up status.';
  }
}

  Widget _photo(int imageId) {
    final future = _photoRequests.putIfAbsent(
      imageId,
          () => widget.service.getPhoto(imageId),
    );

    return FutureBuilder<Uint8List>(
      future: future,
      builder: (context, snapshot) {
        if (snapshot.hasError) {
          return const SizedBox(
            width: 100,
            height: 100,
            child: Center(child: Text('Photo unavailable')),
          );
        }

        if (!snapshot.hasData) {
          return const SizedBox(
            width: 100,
            height: 100,
            child: Center(child: CircularProgressIndicator()),
          );
        }

        return InkWell(
          onTap: () {
            showDialog<void>(
              context: context,
              builder: (_) => Dialog(
                child: InteractiveViewer(
                  child: Image.memory(snapshot.data!),
                ),
              ),
            );
          },
          child: Image.memory(
            snapshot.data!,
            width: 100,
            height: 100,
            fit: BoxFit.cover,
            errorBuilder: (_, __, ___) =>
            const Icon(Icons.broken_image_outlined),
          ),
        );
      },
    );
  }

  Widget _submission(Map<String, dynamic> item) {
    final images = item['images'] as List;
    final status = _text(item['review_status']).replaceAll('_', ' ');

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              _timestamp(item['submitted_at']),
              style: Theme.of(context).textTheme.titleSmall,
            ),
            const SizedBox(height: 8),
            Text('Status: $status'),
            const SizedBox(height: 8),
            Text('Your update: ${_text(item['owner_comment'])}'),
            if (images.isNotEmpty) ...[
              const SizedBox(height: 12),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  for (final image in images)
                    _photo(image['followup_care_image_id'] as int),
                ],
              ),
            ],
            const Divider(height: 24),
            Text(
              item['veterinarian_comment'] == null
                  ? 'Awaiting veterinarian feedback.'
                  : 'Vet feedback: ${item['veterinarian_comment']}',
            ),
            if (item['reviewed_at'] != null)
              Text('Reviewed: ${_timestamp(item['reviewed_at'])}'),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final disabled =
        _submitting || _picking || _blocked || _checkingState;

    return PopScope(
      canPop: !_submitting,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Follow-up Updates'),
          actions: [
            IconButton(
              onPressed: _submitting
                  ? null
                  : () {
                _photoRequests.clear();
                _loadHistory(0);
              },
              icon: const Icon(Icons.refresh),
              tooltip: 'Refresh submissions',
            ),
          ],
        ),
        body: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Reason: ${_text(widget.followup['reason'])}'),
                    const SizedBox(height: 8),
                    Text(
                      'Home care: '
                          '${_text(widget.followup['care_instructions'])}',
                    ),
                    if (_photosRequired) ...[
                      const SizedBox(height: 8),
                      Text(
                        'Photo requirements: '
                            '${_text(widget.followup['photo_instructions'])}',
                      ),
                    ],
                    const SizedBox(height: 8),
                    Text(
                      'In-clinic review required: '
                          '${widget.followup['visit_required'] == true ? 'Yes' : 'No'}',
                    ),
                  ],
                ),
              ),
            ),
            if (_canSubmit && !_checkingState) ...[
              const SizedBox(height: 16),
              TextField(
                controller: _comment,
                enabled: !disabled,
                maxLength: 5000,
                minLines: 3,
                maxLines: 5,
                decoration: const InputDecoration(
                  labelText: 'Progress update',
                  hintText: 'Describe changes since the last review.',
                  border: OutlineInputBorder(),
                ),
              ),
              Wrap(
                spacing: 8,
                children: [
                  OutlinedButton.icon(
                    onPressed: disabled || _photos.length >= 4
                        ? null
                        : () => _pick(ImageSource.camera),
                    icon: const Icon(Icons.camera_alt_outlined),
                    label: const Text('Take Photo'),
                  ),
                  OutlinedButton.icon(
                    onPressed: disabled || _photos.length >= 4
                        ? null
                        : () => _pick(ImageSource.gallery),
                    icon: const Icon(Icons.photo_library_outlined),
                    label: const Text('Choose from Gallery'),
                  ),
                ],
              ),
              Text('${_photos.length}/4 photos selected'),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  for (var index = 0; index < _photos.length; index++)
                    Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Image.memory(
                          _photos[index],
                          width: 100,
                          height: 100,
                          fit: BoxFit.cover,
                        ),
                        TextButton(
                          onPressed: disabled
                              ? null
                              : () => setState(() => _photos.removeAt(index)),
                          child: const Text('Remove'),
                        ),
                      ],
                    ),
                ],
              ),
              const SizedBox(height: 12),
              FilledButton(
                onPressed: disabled ? null : _submit,
                child: Text(_submitting ? 'Submitting…' : 'Submit Update'),
              ),
            ] else
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      if (_checkingState)
                        const LinearProgressIndicator()
                      else ...[
                        Text(
                          _stateError ?? _submissionStatusMessage,
                          style: const TextStyle(height: 1.5),
                        ),
                        if (_stateError != null)
                          TextButton(
                            onPressed: _refreshSubmissionState,
                            child: const Text('Retry'),
                          ),
                      ],
                    ],
                  ),
                ),
              ),
            if (_message != null)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 12),
                child: Text(_message!),
              ),
            const SizedBox(height: 20),
            const SizedBox(height: 24),
            Card(
              clipBehavior: Clip.antiAlias,
              child: ExpansionTile(
                initiallyExpanded: !_canSubmit,
                leading: const Icon(
                  Icons.history_outlined,
                  color: Color(0xFF2549C7),
                ),
                title: const Text(
                  'Previous updates & vet feedback',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                subtitle: const Text(
                  'View your submitted photos and review responses',
                ),
                tilePadding: const EdgeInsets.symmetric(
                  horizontal: 16,
                  vertical: 8,
                ),
                childrenPadding: const EdgeInsets.fromLTRB(12, 0, 12, 16),
                children: [
                  FutureBuilder<List<Map<String, dynamic>>>(
              future: _history,
              builder: (context, snapshot) {
                if (snapshot.connectionState != ConnectionState.done) {
                  return const Padding(
                    padding: EdgeInsets.all(24),
                    child: Center(child: CircularProgressIndicator()),
                  );
                }

                if (snapshot.hasError) {
                  final error = snapshot.error;

                  return Column(
                    children: [
                      Text(
                        error is ApiException
                            ? error.message
                            : 'Unable to load submission history.',
                      ),
                      TextButton(
                        onPressed: () => _loadHistory(_page),
                        child: const Text('Retry'),
                      ),
                    ],
                  );
                }

                final data = snapshot.data!;

                return Column(
                  children: [
                    if (data.isEmpty)
                      const Padding(
                        padding: EdgeInsets.all(16),
                        child: Text('No updates submitted yet.'),
                      ),
                    for (final item in data.take(10)) _submission(item),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        TextButton(
                          onPressed: _page > 0
                              ? () => _loadHistory(_page - 1)
                              : null,
                          child: const Text('Previous'),
                        ),
                        Text('Page ${_page + 1}'),
                        TextButton(
                          onPressed: data.length > 10
                              ? () => _loadHistory(_page + 1)
                              : null,
                          child: const Text('Next'),
                        ),
                      ],
                    ),
                  ],
                );
              },
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
