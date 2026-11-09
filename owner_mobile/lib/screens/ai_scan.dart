import 'dart:async';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import '../services/api_client.dart';
import '../services/dental_assessment_service.dart';
import '../services/pet_service.dart';

import '../services/ai_assessment_review_service.dart';
import 'ai_assessment_reviews.dart';

class AiScanPage extends StatefulWidget {
  final PetService petService;
  final DentalAssessmentService service;

  const AiScanPage({
    super.key,
    required this.petService,
    required this.service,
  });

  @override
  State<AiScanPage> createState() => _AiScanPageState();
}

class _AiScanPageState extends State<AiScanPage>
    with WidgetsBindingObserver {
  final _picker = ImagePicker();
  final Map<String, Future<Uint8List>> _images = {};

  List<Map<String, dynamic>> _pets = [];
  Map<String, dynamic>? _job;

  Uint8List? _photo;
  int? _petId;
  int? _imageId;

  Timer? _timer;

  bool _loading = true;
  bool _busy = false;
  bool _checking = false;
  bool _accessDenied = false;

  String? _error;

  bool get _processing =>
      _job?['status'] == 'queued' || _job?['status'] == 'running';

  bool get _locked => _busy || _checking || _processing;

  bool get _appActive {
    final state = WidgetsBinding.instance.lifecycleState;
    return state == null || state == AppLifecycleState.resumed;
  }

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _loadPets();
  }

  @override
  void dispose() {
    _timer?.cancel();
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    _timer?.cancel();

    if (state == AppLifecycleState.resumed &&
        _processing &&
        !_accessDenied) {
      _checkStatus();
    }
  }

  Future<void> _loadPets() async {
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final pets = <Map<String, dynamic>>[];
      var offset = 0;

      while (true) {
        final batch = await widget.petService.getPets(
          offset: offset,
          limit: 100,
        );

        pets.addAll(batch);

        if (batch.length < 100) break;
        offset += batch.length;
      }

      if (!mounted) return;

      setState(() {
        _pets = pets;
        _petId = pets.isEmpty ? null : pets.first['pet_id'] as int;
      });
    } on ApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } catch (_) {
      if (mounted) {
        setState(() => _error = 'Unable to load your pets.');
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _clearAssessment() {
    _timer?.cancel();
    _imageId = null;
    _job = null;
    _images.clear();
    _error = null;
    _accessDenied = false;
  }

  Future<void> _pickPhoto(ImageSource source) async {
    if (_locked) return;

    setState(() {
      _busy = true;
      _error = null;
    });

    try {
      final file = await _picker.pickImage(
        source: source,
        maxWidth: 2000,
        maxHeight: 2000,
        imageQuality: 90,
      );

      if (file == null) return;

      final bytes = await file.readAsBytes();

      if (bytes.isEmpty || bytes.lengthInBytes > 8 * 1024 * 1024) {
        throw const ApiException('Choose a photo smaller than 8 MB.');
      }

      if (!mounted) return;

      setState(() {
        _clearAssessment();
        _photo = bytes;
      });
    } on ApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } catch (_) {
      if (mounted) {
        setState(() {
          _error = 'Unable to open the photo. Check camera or photo permissions.';
        });
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _startAssessment() async {
    final petId = _petId;
    final photo = _photo;

    if (_locked || petId == null || photo == null || _job != null) {
      return;
    }

    setState(() {
      _busy = true;
      _error = null;
    });

    try {
      // Reuse an already uploaded image if starting the job previously failed.
      if (_imageId == null) {
        final upload = await widget.service.uploadPhoto(petId, photo);

        if (!mounted) return;

        setState(() {
          _imageId = upload['dental_image_id'] as int;
        });
      }

      final job = await widget.service.startAssessment(_imageId!);

      if (!mounted) return;

      setState(() => _job = job);
      _scheduleCheck();
    } on ApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } catch (_) {
      if (mounted) {
        setState(() {
          _error = 'Unable to confirm the assessment request. '
              'Retrying will reuse the uploaded image.';
        });
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _scheduleCheck() {
    _timer?.cancel();

    if (!mounted || !_processing || !_appActive || _accessDenied) {
      return;
    }

    _timer = Timer(
      const Duration(seconds: 5),
      _checkStatus,
    );
  }

  Future<void> _checkStatus() async {
    final jobId = _job?['assessment_job_id'];

    if (!mounted ||
        jobId is! int ||
        _checking ||
        !_appActive ||
        _accessDenied) {
      return;
    }

    _timer?.cancel();
    setState(() => _checking = true);

    try {
      final job = await widget.service.getAssessment(jobId);

      if (!mounted) return;

      setState(() {
        _job = job;
        _error = null;
      });
    } on ApiException catch (error) {
      if (!mounted) return;

      setState(() {
        _error = error.message;
        _accessDenied =
            error.statusCode == 401 || error.statusCode == 403;
      });
    } catch (_) {
      if (mounted) {
        setState(() {
          _error = 'Unable to refresh assessment progress.';
        });
      }
    } finally {
      if (mounted) {
        setState(() => _checking = false);
        _scheduleCheck();
      }
    }
  }

  Future<void> _openImage(Uint8List bytes, String title) async {
    await showDialog<void>(
      context: context,
      builder: (dialogContext) => Dialog(
        child: SizedBox(
          width: MediaQuery.sizeOf(dialogContext).width * 0.9,
          height: MediaQuery.sizeOf(dialogContext).height * 0.8,
          child: Column(
            children: [
              ListTile(
                title: Text(title),
                trailing: IconButton(
                  tooltip: 'Close image',
                  onPressed: () => Navigator.of(dialogContext).pop(),
                  icon: const Icon(Icons.close),
                ),
              ),
              Expanded(
                child: InteractiveViewer(
                  minScale: 0.5,
                  maxScale: 5,
                  child: Center(
                    child: Image.memory(bytes, fit: BoxFit.contain),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _resultImage(String kind, String title) {
    final jobId = _job!['assessment_job_id'] as int;

    final future = _images.putIfAbsent(
      kind,
          () => widget.service.getResultImage(jobId, kind),
    );

    return Card(
      margin: const EdgeInsets.only(bottom: 16),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 12),
            FutureBuilder<Uint8List>(
              future: future,
              builder: (context, snapshot) {
                if (snapshot.hasError) {
                  return TextButton.icon(
                    onPressed: () {
                      setState(() => _images.remove(kind));
                    },
                    icon: const Icon(Icons.refresh),
                    label: const Text('Retry loading image'),
                  );
                }

                final bytes = snapshot.data;

                if (bytes == null) {
                  return const SizedBox(
                    height: 160,
                    child: Center(child: CircularProgressIndicator()),
                  );
                }

                return InkWell(
                  onTap: () => _openImage(bytes, title),
                  child: Column(
                    children: [
                      Image.memory(
                        bytes,
                        height: 220,
                        width: double.infinity,
                        fit: BoxFit.contain,
                      ),
                      const SizedBox(height: 8),
                      const Text('Tap to enlarge · Pinch to zoom'),
                    ],
                  ),
                );
              },
            ),
          ],
        ),
      ),
    );
  }

  static const _conditionInformation = {
    'healthy': {
      'title': 'Healthy appearance',
      'description':
      'This is the model’s healthy-image category, not a dental disease. '
          'A healthy-looking photo does not rule out problems elsewhere '
          'in the mouth or below the gumline.',
    },
    'plaque': {
      'title': 'Dental plaque',
      'description':
      'Plaque is a soft, sticky film containing bacteria that collects '
          'on the teeth. Plaque near the gumline can contribute to gum '
          'inflammation. It can harden into calculus over time.',
    },
    'gingivitis': {
      'title': 'Gingivitis',
      'description':
      'Gingivitis means inflammation of the gums, commonly associated '
          'with bacterial plaque. The gums may appear red or swollen and '
          'may bleed. A veterinary examination is needed to assess the '
          'gums and check for deeper periodontal disease.',
    },
    'calculus': {
      'title': 'Dental calculus / tartar',
      'description':
      'Calculus, also called tartar, forms when minerals in saliva '
          'harden dental plaque. It may appear as a yellow or brown deposit '
          'on the teeth. Visible tartar alone does not show the full '
          'condition of the gums or tissues beneath them.',
    },
  };

  Widget _predictionCard(Map<dynamic, dynamic> prediction) {
    final condition =
        prediction['condition']?.toString().toLowerCase() ?? '';

    final information = _conditionInformation[condition];
    final positive = prediction['positive'] == true;
    final healthy = condition == 'healthy';
    final score = prediction['confidence'];

    final title = information?['title'] ?? condition;
    final description = information?['description'] ??
        'Ask your veterinarian to explain this screening result.';

    final colour = positive && !healthy
        ? const Color(0xFF9A5A16)
        : const Color(0xFF2549C7);

    final status = healthy
        ? (positive
        ? 'Healthy appearance suggested by the model'
        : 'Healthy-image category below threshold')
        : (positive
        ? 'Possible finding — veterinary review needed'
        : 'Not flagged in this photo');

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      clipBehavior: Clip.antiAlias,
      child: ExpansionTile(
        key: PageStorageKey('condition-$condition'),
        initiallyExpanded: positive && !healthy,
        tilePadding: const EdgeInsets.symmetric(
          horizontal: 16,
          vertical: 6,
        ),
        childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 18),
        leading: CircleAvatar(
          backgroundColor: colour.withValues(alpha: 0.10),
          child: Icon(
            healthy
                ? Icons.check_circle_outline
                : Icons.info_outline,
            color: colour,
          ),
        ),
        title: Text(
          title,
          style: const TextStyle(fontWeight: FontWeight.w700),
        ),
        subtitle: Padding(
          padding: const EdgeInsets.only(top: 6),
          child: Text(
            '$status\n'
                'Model score: ${score is num ? '${(score * 100).toStringAsFixed(1)}%' : 'Unavailable'}',
            style: const TextStyle(height: 1.5),
          ),
        ),
        children: [
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Divider(),
              const SizedBox(height: 8),
              const Text(
                'What does this mean?',
                style: TextStyle(fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 8),
              Text(
                description,
                style: const TextStyle(height: 1.6),
              ),
              const SizedBox(height: 12),
              Text(
                positive && !healthy
                    ? 'The AI flagged a possible finding. '
                    'Your veterinarian must confirm its meaning.'
                    : 'A result below the threshold does not rule out '
                    'a dental problem.',
                style: TextStyle(
                  fontSize: 12,
                  height: 1.5,
                  color: Colors.grey.shade700,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Future<void> _openVetReviews({int? analysisId}) async {
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => AIAssessmentReviewsScreen(
          service: AIAssessmentReviewService(widget.service.api),
          analysisId: analysisId,
        ),
      ),
    );
  }

  Widget _assessmentStatus() {
    final status = _job?['status'];
    final result = _job?['result'];

    if (status == 'completed' && result is Map) {
      final predictions = result['predictions'] as List? ?? [];
      final severity = result['severity'];

      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SizedBox(height: 24),
          Text(
            'Assessment results',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 8),
          Text(
            result['interpretation']?.toString() ??
                'AI screening results require veterinary review.',
          ),
          const SizedBox(height: 16),

          for (final prediction in predictions)
            if (prediction is Map)
              _predictionCard(prediction),

          const Padding(
            padding: EdgeInsets.symmetric(vertical: 12),
            child: Text(
              'Percentages are model scores, not a confirmed diagnosis.',
              style: TextStyle(fontSize: 12),
            ),
          ),

          if (severity is Map) ...[
            Text(
              'Experimental severity estimate: ${severity['label']}',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            Text(severity['reason']?.toString() ?? ''),
            const SizedBox(height: 20),
          ],

          if (_job?['analysis_id'] is int) ...[
            FilledButton.icon(
              onPressed: () => _openVetReviews(
                analysisId: _job!['analysis_id'] as int,
              ),
              icon: const Icon(Icons.medical_services_outlined),
              label: const Text('Request vet review'),
            ),
            const SizedBox(height: 16),
          ],

          _resultImage('heatmap', 'Model attention'),
          _resultImage('segmentation', 'Predicted image regions'),
          _resultImage('summary', 'Assessment summary'),
        ],
      );
    }

    if (status == 'rejected' || status == 'failed') {
      return Padding(
        padding: const EdgeInsets.only(top: 20),
        child: Text(
          _job?['message']?.toString() ??
              'The assessment could not be completed. Choose another photo.',
        ),
      );
    }

    if (_processing) {
      return Card(
        margin: const EdgeInsets.only(top: 20),
        child: Padding(
          padding: const EdgeInsets.all(18),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const LinearProgressIndicator(),
              const SizedBox(height: 16),
              Text(
                status == 'queued'
                    ? 'Waiting for assessment…'
                    : 'Analysing your pet’s dental photo…',
              ),
              const SizedBox(height: 8),
              const Text(
                'Processing may take a few minutes.',
                style: TextStyle(fontSize: 12),
              ),
              TextButton.icon(
                onPressed: _checking || _accessDenied
                    ? null
                    : _checkStatus,
                icon: const Icon(Icons.refresh),
                label: const Text('Check progress'),
              ),
            ],
          ),
        ),
      );
    }

    return const SizedBox.shrink();
  }

  @override
  Widget build(BuildContext context) {
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
              Text(_error ?? 'Add a pet before starting an assessment.'),
              const SizedBox(height: 12),
              OutlinedButton(
                onPressed: _loadPets,
                child: const Text('Reload pets'),
              ),
            ],
          ),
        ),
      );
    }

    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        Text(
          'AI Dental Assessment',
          style: Theme.of(context).textTheme.headlineSmall,
        ),
        const SizedBox(height: 8),
        const Text(
          'Select your pet and take a clear photo of their teeth and gums.',
        ),
        const SizedBox(height: 24),

        DropdownButtonFormField<int>(
          key: ValueKey(_petId),
          initialValue: _petId,
          isExpanded: true,
          decoration: const InputDecoration(labelText: 'Your pet'),
          items: [
            for (final pet in _pets)
              DropdownMenuItem(
                value: pet['pet_id'] as int,
                child: Text(
                  '${pet['pet_name']} · ${pet['species']}',
                  overflow: TextOverflow.ellipsis,
                ),
              ),
          ],
          onChanged: _locked
              ? null
              : (value) {
            setState(() {
              _clearAssessment();
              _petId = value;
              _photo = null;
            });
          },
        ),
        const SizedBox(height: 20),

        if (_photo != null)
          ClipRRect(
            borderRadius: BorderRadius.circular(16),
            child: Image.memory(
              _photo!,
              height: 240,
              fit: BoxFit.contain,
            ),
          )
        else
          Container(
            height: 180,
            decoration: BoxDecoration(
              color: const Color(0xFFE8EDFF),
              borderRadius: BorderRadius.circular(16),
            ),
            child: const Icon(
              Icons.add_a_photo_outlined,
              size: 48,
              color: Color(0xFF2549C7),
            ),
          ),

        const SizedBox(height: 16),
        Row(
          children: [
            Expanded(
              child: OutlinedButton.icon(
                onPressed: _locked
                    ? null
                    : () => _pickPhoto(ImageSource.camera),
                icon: const Icon(Icons.camera_alt_outlined),
                label: const Text('Camera'),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: OutlinedButton.icon(
                onPressed: _locked
                    ? null
                    : () => _pickPhoto(ImageSource.gallery),
                icon: const Icon(Icons.photo_library_outlined),
                label: const Text('Gallery'),
              ),
            ),
          ],
        ),

        if (_error != null)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 12),
            child: Text(
              _error!,
              style: TextStyle(
                color: Theme.of(context).colorScheme.error,
              ),
            ),
          ),

        const SizedBox(height: 12),
        FilledButton.icon(
          onPressed: _locked || _photo == null || _job != null
              ? null
              : _startAssessment,
          icon: const Icon(Icons.auto_awesome_outlined),
          label: Text(
            _busy ? 'Please wait…' : 'Start assessment',
          ),
        ),

        const SizedBox(height: 12),
        OutlinedButton.icon(
          onPressed: _locked ? null : () => _openVetReviews(),
          icon: const Icon(Icons.mark_chat_read_outlined),
          label: const Text('My vet reviews & feedback'),
        ),

        _assessmentStatus(),
        const SizedBox(height: 24),
      ],
    );
  }
}