import 'dart:async';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import '../services/api_client.dart';
import '../services/dental_assessment_service.dart';
import '../services/pet_service.dart';

import '../services/ai_assessment_review_service.dart';
import 'ai_assessment_reviews.dart';

import 'assessment_history.dart';

import '../services/appointment_service.dart';
import 'clinic_picker.dart';
import 'book_appointment.dart';

import 'pdf_preview.dart';
import '../services/assessment_pdf_service.dart';

class AiScanPage extends StatefulWidget {
  final PetService petService;
  final DentalAssessmentService service;
  final int? initialPetId;
  final int? initialAssessmentJobId;
  final Map<String, dynamic>? _completedJob;

  const AiScanPage({
    super.key,
    required this.petService,
    required this.service,
    this.initialPetId,
    this.initialAssessmentJobId,
  }) : _completedJob = null;

  const AiScanPage._result({
    required this.petService,
    required this.service,
    required Map<String, dynamic> job,
  }) : _completedJob = job,
       initialPetId = null,
       initialAssessmentJobId = null;

  @override
  State<AiScanPage> createState() => _AiScanPageState();
}

class _AiScanPageState extends State<AiScanPage> with WidgetsBindingObserver {
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
  bool _historyOpen = false;
  bool _openingBooking = false;
  bool _exportingPdf = false;

  String? _error;
  String? _progressNote;
  int _pollFailures = 0;
  int? _openedResultJobId;
  bool _resultOpen = false;
  bool _showSummaryImage = false;

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
    if (widget._completedJob != null) {
      _job = widget._completedJob;
      _loading = false;
    } else {
      _loadPets();
    }
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

        if (!mounted) return;

        pets.addAll(batch);

        if (batch.length < 100) break;
        offset += batch.length;
      }

      var selectedId = widget.initialPetId;

      if (selectedId != null &&
          !pets.any((pet) => pet['pet_id'] == selectedId)) {
        throw const ApiException(
          'The selected pet is no longer available.',
        );
      }

      Map<String, dynamic>? initialJob;
      final jobId = widget.initialAssessmentJobId;

      if (jobId != null) {
        initialJob = await widget.service.getAssessment(jobId);

        if (!mounted) return;

        final jobPetId = initialJob['pet_id'];

        if (jobPetId is! int ||
            !pets.any((pet) => pet['pet_id'] == jobPetId)) {
          throw const ApiException(
            'The assessment pet could not be verified.',
          );
        }

        if (selectedId != null && selectedId != jobPetId) {
          throw const ApiException(
            'This assessment does not belong to the selected pet.',
          );
        }

        selectedId = jobPetId;
      }

      selectedId ??= pets.isEmpty
          ? null
          : pets.first['pet_id'] as int;

      if (!mounted) return;

      setState(() {
        _pets = pets;
        _petId = selectedId;
        _job = initialJob;
        _imageId = initialJob?['dental_image_id'] as int?;
        _images.clear();
        _accessDenied = false;
      });

      _scheduleCheck();
    } on ApiException catch (error) {
      if (mounted) {
        setState(() => _error = error.message);
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          _error = 'Unable to load the selected pet or assessment.';
        });
      }
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  void _clearAssessment() {
    _timer?.cancel();
    _imageId = null;
    _job = null;
    _progressNote = null;
    _pollFailures = 0;
    _openedResultJobId = null;
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

  Future<void> _showCompletedResult({bool reopen = false}) async {
    final job = _job;
    final id = job?['assessment_job_id'];
    if (!mounted ||
        widget._completedJob != null ||
        _resultOpen ||
        job == null ||
        job['status'] != 'completed' ||
        job['result'] is! Map ||
        id is! int ||
        (!reopen && _openedResultJobId == id)) {
      return;
    }

    _timer?.cancel();
    _openedResultJobId = id;
    _resultOpen = true;
    try {
      await Navigator.of(context).push<void>(
        MaterialPageRoute(
          builder: (_) => AiScanPage._result(
            petService: widget.petService,
            service: widget.service,
            job: Map<String, dynamic>.unmodifiable(job),
          ),
        ),
      );
    } finally {
      _resultOpen = false;
    }
  }

  void _scheduleCheck() {
    _timer?.cancel();
    if (!mounted || widget._completedJob != null) return;

    if (_job?['status'] == 'completed') {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted && _appActive) _showCompletedResult();
      });
      return;
    }

    if (!_processing || !_appActive || _accessDenied) return;
    const delays = [3, 6, 12, 20];
    _timer = Timer(Duration(seconds: delays[_pollFailures]), _checkStatus);
  }

  Future<void> _checkStatus() async {
    final jobId = _job?['assessment_job_id'];
    if (!mounted ||
        jobId is! int ||
        !_processing ||
        _checking ||
        !_appActive ||
        _accessDenied) {
      return;
    }

    _timer?.cancel();
    setState(() => _checking = true);
    try {
      final job = await widget.service.getAssessment(jobId);
      if (!mounted ||
          _job?['assessment_job_id'] != jobId ||
          !_processing) {
        return;
      }
      setState(() {
        _job = job;
        _error = null;
        _progressNote = null;
        _pollFailures = 0;
      });
    } catch (error) {
      if (!mounted ||
          _job?['assessment_job_id'] != jobId ||
          !_processing) {
        return;
      }
      final status = error is ApiException ? error.statusCode : null;
      setState(() {
        _accessDenied = status == 401 || status == 403 || status == 404;
        if (_accessDenied) {
          _error = error.toString();
          _progressNote = null;
        } else {
          if (_pollFailures < 3) _pollFailures++;
          _progressNote = 'Connection interrupted. Your assessment may '
              'still be processing. Retrying the same assessment…';
        }
      });
    } finally {
      if (mounted) {
        setState(() => _checking = false);
        _scheduleCheck();
      }
    }
  }

  Future<void> _openImage(Uint8List bytes, String title) async {
    await Navigator.of(context).push<void>(
      MaterialPageRoute(
        builder: (_) => Scaffold(
          backgroundColor: Colors.black,
          appBar: AppBar(
            backgroundColor: Colors.black,
            foregroundColor: Colors.white,
            title: Text(title),
          ),
          body: SafeArea(
            child: LayoutBuilder(
              builder: (context, constraints) => InteractiveViewer(
                minScale: 1,
                maxScale: 6,
                child: SizedBox(
                  width: constraints.maxWidth,
                  height: constraints.maxHeight,
                  child: Image.memory(bytes, fit: BoxFit.contain),
                ),
              ),
            ),
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
            if (title.isNotEmpty)
              Text(
                title,
                style: Theme.of(context).textTheme.titleMedium,
              ),
            if (kind == 'segmentation') ...[
              const SizedBox(height: 12),
              Wrap(spacing: 16, runSpacing: 8, children: [
                _legend(const Color(0xFFFF0000), 'Predicted gingivitis'),
                _legend(
                  _job?['result']?['segmentation_palette'] == 'red-yellow-v1'
                      ? const Color(0xFFFFD600)
                      : const Color(0xFF00FF00),
                  'Predicted calculus',
                ),
              ]),
              const SizedBox(height: 8),
              const Text(
                'Colours mark model-predicted regions, not confirmed '
                'disease. Uncoloured areas do not establish healthy tissue.',
                style: TextStyle(fontSize: 12),
              ),
            ],
            if (kind == 'heatmap') ...[
              const SizedBox(height: 8),
              const Text(
                'Heatmap colours show model attention strength. They '
                'use a different colour scale from segmentation.',
                style: TextStyle(fontSize: 12),
              ),
            ],
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
                  onTap: () => _openImage(
                    bytes,
                    title.isEmpty ? 'Combined AI view' : title,
                  ),
                  child: Column(
                    children: [
                      Image.memory(
                        bytes,
                        height: kind == 'summary' ? 420 : 220,
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
    final assessed = prediction['assessed'] != false &&
        prediction['positive'] is bool;
    final positive = assessed && prediction['positive'] == true;
    final healthy = condition == 'healthy';
    final score = prediction['confidence'];

    final title = information?['title'] ?? condition;
    final description = information?['description'] ??
        'Ask your veterinarian to explain this screening result.';

    final colour = !assessed
        ? const Color(0xFF64748B)
        : positive && !healthy
        ? const Color(0xFF9A5A16)
        : const Color(0xFF2549C7);

    final String status;

    if (!assessed) {
      status = 'Not assessed for this species';
    } else if (healthy) {
      status = positive
          ? 'Healthy appearance suggested by the model'
          : 'Healthy-image category below threshold';
    } else {
      status = positive
          ? 'Possible finding — veterinary review needed'
          : 'Not flagged in this photo';
    }

    final subtitle = !assessed
        ? status
        : '$status\nModel score: '
        '${score is num ? '${(score * 100).toStringAsFixed(1)}%' : 'Unavailable'}';

    final explanation = !assessed
        ? 'This classifier has insufficient labelled data to assess '
        'this condition reliably for this species. '
        'Not assessed does not mean absent.'
        : positive && !healthy
        ? 'The AI flagged a possible finding. '
        'Your veterinarian must confirm its meaning.'
        : 'A result below the threshold does not rule out '
        'a dental problem.';

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
            !assessed
                ? Icons.help_outline_rounded
                : healthy && positive
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
            subtitle,
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
                'About this condition',
                style: TextStyle(fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 8),
              Text(
                description,
                style: const TextStyle(height: 1.6),
              ),
              const SizedBox(height: 12),
              Text(
                explanation,
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

  Future<void> _openHistory() async {
    final petId = _petId;

    if (_historyOpen ||
        _locked ||
        petId == null ||
        _pets.isEmpty) {
      return;
    }

    setState(() => _historyOpen = true);

    try {
      await Navigator.of(context).push<void>(
        MaterialPageRoute(
          builder: (_) => AssessmentHistoryScreen(
            service: widget.service,
            pets: _pets,
            initialPetId: petId,
            onOpen: (item) async {
              final job = await widget.service.getAssessment(
                item['assessment_job_id'] as int,
              );

              if (!mounted) return;

              if (job['pet_id'] != item['pet_id']) {
                throw const ApiException(
                  'The assessment pet does not match.',
                );
              }

              final complete =
                  job['status'] == 'completed' &&
                      job['result'] is Map;

              await Navigator.of(context).push<void>(
                MaterialPageRoute(
                  builder: (_) => complete
                      ? AiScanPage._result(
                    petService: widget.petService,
                    service: widget.service,
                    job: Map<String, dynamic>.unmodifiable(job),
                  )
                      : Scaffold(
                    appBar: AppBar(
                      title: const Text('Assessment details'),
                    ),
                    body: AiScanPage(
                      petService: widget.petService,
                      service: widget.service,
                      initialPetId: item['pet_id'] as int,
                      initialAssessmentJobId:
                      item['assessment_job_id'] as int,
                    ),
                  ),
                ),
              );
            },
          ),
        ),
      );
    } finally {
      if (mounted) {
        setState(() => _historyOpen = false);
      }
    }
  }

  Future<void> _downloadAssessmentPdf() async {
    if (_exportingPdf) return;

    final jobId = _job?['assessment_job_id'];
    if (jobId is! int) return;

    setState(() => _exportingPdf = true);

    try {
      // Retrieve the authorized saved assessment before exporting.
      final job = await widget.service.getAssessment(jobId);

      if (!mounted) return;

      final petId = job['pet_id'];
      final imageId = job['dental_image_id'];

      if (job['status'] != 'completed' ||
          petId is! int ||
          imageId is! int) {
        throw const ApiException(
          'This assessment is not ready for PDF export.',
        );
      }

      final pet = await widget.petService.getPet(petId);
      if (!mounted) return;

      final original = await widget.service.api.getBytes(
        '/dental-images/$imageId/file',
      );
      if (!mounted) return;

      final combined = await widget.service.getResultImage(
        jobId,
        'summary',
      );
      if (!mounted) return;

      final bytes = await AssessmentPdfService.build(
        job: job,
        pet: pet,
        originalImage: original,
        combinedImage: combined,
      );

      if (!mounted) return;

      await Navigator.of(context).push<void>(
        MaterialPageRoute(
          builder: (_) => ReportPdfPreviewPage(
            bytes: bytes,
            filename: 'VetDental_Assessment_$jobId.pdf',
            title: 'AI assessment report',
          ),
        ),
      );
    } catch (error) {
      if (!mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            error is ApiException
                ? error.message
                : 'Could not prepare the PDF. Check your connection '
                'and try again.',
          ),
        ),
      );
    } finally {
      if (mounted) {
        setState(() => _exportingPdf = false);
      }
    }
  }

  Future<void> _bookDentalExamination() async {
    if (_openingBooking) return;

    final petId = _job?['pet_id'];
    final analysisId = _job?['analysis_id'];

    if (petId is! int || analysisId is! int) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'The pet linked to this assessment could not be identified.',
          ),
        ),
      );
      return;
    }

    setState(() => _openingBooking = true);

    try {
      final appointments = AppointmentService(widget.service.api);

      final clinic = await Navigator.of(context)
          .push<Map<String, dynamic>>(
        MaterialPageRoute(
          builder: (_) => ClinicPickerScreen(
            service: appointments,
          ),
        ),
      );

      if (!mounted || clinic == null) return;

      await Navigator.of(context).push<bool>(
        MaterialPageRoute(
          builder: (_) => BookAppointmentScreen(
            clinic: clinic,
            service: appointments,
            petService: widget.petService,
            initialPetId: petId,
            aiAnalysisId: analysisId,
          ),
        ),
      );
    } catch (_) {
      if (!mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Could not open booking. Please try again.',
          ),
        ),
      );
    } finally {
      if (mounted) {
        setState(() => _openingBooking = false);
      }
    }
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

  Widget _legend(Color colour, String label) {
    return Row(mainAxisSize: MainAxisSize.min, children: [
      Container(width: 14, height: 14,
          decoration: BoxDecoration(color: colour,
              borderRadius: BorderRadius.circular(4))),
      const SizedBox(width: 6),
      Text(label, style: const TextStyle(fontSize: 12)),
    ]);
  }

  Widget _summaryCard(Map result) {
    final rawPredictions = result['predictions'];

    final predictions = rawPredictions is List
        ? rawPredictions.whereType<Map>().toList()
        : <Map>[];

    final notAssessed = predictions
        .where((prediction) => prediction['assessed'] == false)
        .map((prediction) => prediction['condition'].toString())
        .toList();

    final diseaseFindings = predictions.where(
          (prediction) =>
      {'plaque', 'gingivitis', 'calculus'}
          .contains(prediction['condition']) &&
          prediction['positive'] == true,
    ).toList();

    final decision = result['decision'];
    final severity = result['severity'];

    final status = decision is Map
        ? decision['status']?.toString() ?? 'unavailable'
        : 'unavailable';

    final severityLabel = severity is Map
        ? severity['label']?.toString() ?? 'Unavailable'
        : 'Unavailable';

    final decisionReason = decision is Map
        ? decision['reason']?.toString() ?? ''
        : '';

    final severityReason = severity is Map
        ? severity['reason']?.toString() ?? ''
        : '';

    final String heading;
    final String label;
    final String explanation;

    if (status == 'inconclusive') {
      heading = 'Result needs review';
      label = 'Inconclusive';
      explanation = decisionReason;
    } else if (status == 'healthy_pattern') {
      heading = 'Image screening result';
      label = 'No supported disease flags';
      explanation = decisionReason;
    } else if (status == 'disease_flags' &&
        {'Mild', 'Moderate', 'Severe'}.contains(severityLabel)) {
      heading = 'Experimental severity estimate';
      label = severityLabel;
      explanation = severityReason;
    } else if (status == 'disease_flags') {
      heading = 'Image screening result';
      label = 'Severity unavailable';
      explanation = decisionReason;
    } else {
      heading = 'Result unavailable';
      label = 'Unavailable';
      explanation = decisionReason.isNotEmpty
          ? decisionReason
          : 'Reopen this assessment after updating the backend.';
    }

    final needsReview = status == 'inconclusive' ||
        status == 'unavailable' ||
        label == 'Severity unavailable';

    final accent = needsReview
        ? const Color(0xFFFFD493)
        : const Color(0xFFD1F04B);

    return Container(
      padding: const EdgeInsets.all(22),
      decoration: BoxDecoration(
        color: const Color(0xFF172333),
        borderRadius: BorderRadius.circular(22),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                needsReview
                    ? Icons.info_outline_rounded
                    : Icons.auto_awesome,
                color: accent,
              ),
              const SizedBox(width: 10),
              const Expanded(
                child: Text(
                  'Assessment summary',
                  style: TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 22),
          Text(
            heading,
            style: const TextStyle(color: Colors.white70),
          ),
          const SizedBox(height: 6),
          Text(
            label,
            style: TextStyle(
              color: accent,
              fontSize: 26,
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 14),
          if (explanation.isNotEmpty)
            Text(
              explanation,
              style: const TextStyle(
                color: Colors.white,
                height: 1.5,
              ),
            ),
          if (notAssessed.isNotEmpty) ...[
            const SizedBox(height: 14),
            Text(
              'Not assessed: ${notAssessed.join(', ')}. '
                  'These conditions have not been ruled out.',
              style: const TextStyle(
                color: Colors.white70,
                height: 1.5,
              ),
            ),
          ],
          if (diseaseFindings.isNotEmpty) ...[
            const SizedBox(height: 14),
            Text(
              'Model flags: ${diseaseFindings.map(
                    (item) => item['condition'],
              ).join(', ')}',
              style: const TextStyle(
                color: Colors.white70,
                height: 1.5,
              ),
            ),
          ],
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 16),
            child: Divider(color: Colors.white24),
          ),
          const Text(
            'AI screening reference. A veterinarian can review '
                'the image and clinical findings.',
            style: TextStyle(
              color: Colors.white70,
              height: 1.5,
            ),
          ),
        ],
      ),
    );
  }

  Widget _assessmentStatus() {
    final status = _job?['status'];
    final result = _job?['result'];

    if (status == 'completed' && result is Map) {
      if (widget._completedJob == null) {
        return Card(
          margin: const EdgeInsets.only(top: 20),
          child: Padding(
            padding: const EdgeInsets.all(18),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('Assessment ready',
                    style: TextStyle(fontWeight: FontWeight.w700)),
                const SizedBox(height: 8),
                const Text('Your result is saved. Open it to view the findings.'),
                const SizedBox(height: 12),
                FilledButton.icon(
                  onPressed: () => _showCompletedResult(reopen: true),
                  icon: const Icon(Icons.arrow_forward),
                  label: const Text('View assessment'),
                ),
                TextButton(
                  onPressed: () => setState(() {
                    _clearAssessment();
                    _photo = null;
                  }),
                  child: const Text('Scan another photo'),
                ),
              ],
            ),
          ),
        );
      }
      final predictions = result['predictions'] as List? ?? [];


      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _summaryCard(result),
          const SizedBox(height: 20),
          Text('Findings in this photo',
              style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 12),
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

          const Text(
            'A photo cannot confirm dental health. If you are '
                'concerned about the findings, arrange a dental examination.',
            style: TextStyle(height: 1.5),
          ),
          const SizedBox(height: 12),
          SizedBox(
            width: double.infinity,
            child: FilledButton.icon(
              onPressed: _openingBooking
                  ? null
                  : _bookDentalExamination,
              icon: const Icon(Icons.calendar_month_outlined),
              label: Text(
                _openingBooking
                    ? 'Opening booking…'
                    : 'Book a dental examination',
              ),
            ),
          ),

          const SizedBox(height: 10),
          SizedBox(
            width: double.infinity,
            child: OutlinedButton.icon(
              onPressed: _exportingPdf
                  ? null
                  : _downloadAssessmentPdf,
              icon: const Icon(Icons.download_outlined),
              label: Text(
                _exportingPdf
                    ? 'Preparing PDF…'
                    : 'Download PDF',
              ),
            ),
          ),
          const SizedBox(height: 20),

          _resultImage('heatmap', 'Model attention'),
          _resultImage('segmentation', 'Predicted image regions'),
          Card(
            child: ExpansionTile(
              title: const Text('Combined AI view'),
              subtitle: const Text('Heatmap with predicted region outlines'),
              onExpansionChanged: (open) =>
                  setState(() => _showSummaryImage = open),
              children: [
                if (_showSummaryImage)
                  _resultImage('summary', ''),
              ],
            ),
          ),
        ],
      );
    }

    if (status == 'rejected' || status == 'failed') {
      final rejected = status == 'rejected';
      final message = _job?['message']?.toString().trim();

      return Container(
        margin: const EdgeInsets.only(top: 20),
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: rejected
              ? const Color(0xFFFFF8EB)
              : const Color(0xFFF2F5FC),
          borderRadius: BorderRadius.circular(18),
          border: Border.all(
            color: rejected
                ? const Color(0xFFEAD6A8)
                : const Color(0xFFD6E0F1),
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  rejected
                      ? Icons.add_photo_alternate_outlined
                      : Icons.cloud_off_outlined,
                  color: const Color(0xFF53657C),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    rejected
                        ? 'Please try another photo'
                        : 'Assessment could not finish',
                    style: const TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.w700,
                      color: Color(0xFF203A5C),
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Text(
              message != null && message.isNotEmpty
                  ? message
                  : rejected
                  ? 'We could not assess this photo reliably.'
                  : 'Processing was interrupted. Please try again later.',
              style: const TextStyle(
                height: 1.6,
                color: Color(0xFF53657C),
              ),
            ),
            if (rejected) ...[
              const SizedBox(height: 16),
              const Text(
                'For a clearer dental photo',
                style: TextStyle(fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 8),
              const Text(
                '• Use an original, sharp photo in good lighting.\n'
                    '• Include the teeth and nearby gumline clearly.\n'
                    '• Avoid glare, heavy cropping and blurry images.\n'
                    '• Only photograph your pet if it is comfortable. '
                    'Do not force its mouth open.',
                style: TextStyle(height: 1.7),
              ),
              const SizedBox(height: 18),
              Wrap(
                spacing: 10,
                runSpacing: 10,
                children: [
                  FilledButton.icon(
                    onPressed: _locked
                        ? null
                        : () => _pickPhoto(ImageSource.camera),
                    icon: const Icon(Icons.camera_alt_outlined),
                    label: const Text('Retake photo'),
                  ),
                  OutlinedButton.icon(
                    onPressed: _locked
                        ? null
                        : () => _pickPhoto(ImageSource.gallery),
                    icon: const Icon(Icons.photo_library_outlined),
                    label: const Text('Choose another photo'),
                  ),
                ],
              ),
            ],
            const SizedBox(height: 12),
            const Text(
              'No assessment result was generated.',
              style: TextStyle(
                fontSize: 12,
                color: Color(0xFF64748B),
              ),
            ),
          ],
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
                'Your photo is processed in the background.',
                style: TextStyle(fontSize: 12),
              ),
              if (_progressNote != null) ...[
                const SizedBox(height: 8),
                Text(_progressNote!, style: const TextStyle(fontSize: 12)),
              ],
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

  Widget _processingView() {
    final queued = _job?['status'] == 'queued';
    final reconnecting = _progressNote != null;

    final title = _busy
        ? 'Preparing your assessment'
        : reconnecting
        ? 'Reconnecting to your assessment'
        : queued
        ? 'Your assessment is queued'
        : 'Analysing your pet’s photo';

    final description = _busy
        ? 'Uploading your photo and submitting the request.'
        : queued
        ? 'Waiting for the assessment worker to start.'
        : 'The AI is processing the photo. Your result will '
        'open automatically when it is ready.';

    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        Container(
          padding: const EdgeInsets.all(24),
          decoration: BoxDecoration(
            gradient: const LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [
                Color(0xFF17368F),
                Color(0xFF4269E8),
              ],
            ),
            borderRadius: BorderRadius.circular(28),
          ),
          child: Column(
            children: [
              const Text(
                'AI DENTAL ASSESSMENT',
                style: TextStyle(
                  color: Color(0xFFDCE5FF),
                  fontSize: 11,
                  fontWeight: FontWeight.w700,
                  letterSpacing: 1.5,
                ),
              ),
              const SizedBox(height: 28),
              SizedBox(
                width: 170,
                height: 170,
                child: Stack(
                  alignment: Alignment.center,
                  children: [
                    const SizedBox.expand(
                      child: CircularProgressIndicator(
                        strokeWidth: 3,
                        color: Color(0xFFB7D8FF),
                        backgroundColor: Color(0xFF5878D2),
                      ),
                    ),
                    ClipRRect(
                      borderRadius: BorderRadius.circular(65),
                      child: _photo != null
                          ? Image.memory(
                        _photo!,
                        width: 130,
                        height: 130,
                        fit: BoxFit.cover,
                      )
                          : Container(
                        width: 130,
                        height: 130,
                        color: const Color(0xFF3559BD),
                        child: const Icon(
                          Icons.image_search_rounded,
                          color: Colors.white,
                          size: 48,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 28),
              Text(
                title,
                textAlign: TextAlign.center,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 23,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 12),
              Text(
                description,
                textAlign: TextAlign.center,
                style: const TextStyle(
                  color: Color(0xFFE0E8FF),
                  height: 1.5,
                ),
              ),
              const SizedBox(height: 24),
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 14,
                  vertical: 9,
                ),
                decoration: BoxDecoration(
                  color: const Color(0xFF294BAA),
                  borderRadius: BorderRadius.circular(20),
                ),
                child: Text(
                  _busy
                      ? 'SUBMITTING'
                      : queued
                      ? 'QUEUED'
                      : 'PROCESSING',
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 11,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 1,
                  ),
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 20),
        const Card(
          child: Padding(
            padding: EdgeInsets.all(18),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(
                  Icons.info_outline_rounded,
                  color: Color(0xFF2549C7),
                ),
                SizedBox(width: 12),
                Expanded(
                  child: Text(
                    'Processing time varies. AI results are screening '
                        'references and do not replace a veterinary examination.',
                    style: TextStyle(height: 1.5),
                  ),
                ),
              ],
            ),
          ),
        ),
        if (_progressNote != null) ...[
          const SizedBox(height: 12),
          Text(
            _progressNote!,
            textAlign: TextAlign.center,
          ),
        ],
        if (_error != null) ...[
          const SizedBox(height: 12),
          Text(
            _error!,
            textAlign: TextAlign.center,
            style: TextStyle(
              color: Theme.of(context).colorScheme.error,
            ),
          ),
        ],
        if (_processing) ...[
          const SizedBox(height: 16),
          OutlinedButton.icon(
            onPressed: _checking || _accessDenied
                ? null
                : _checkStatus,
            icon: const Icon(Icons.refresh_rounded),
            label: Text(
              _checking ? 'Checking status…' : 'Check progress',
            ),
          ),
        ],
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    if (widget._completedJob != null) {
      return Scaffold(
        appBar: AppBar(title: const Text('Dental assessment')),
        body: ListView(
          padding: const EdgeInsets.all(20),
          children: [_assessmentStatus(), const SizedBox(height: 24)],
        ),
      );
    }
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_processing || (_busy && _photo != null)) {
      return _processingView();
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

        const SizedBox(height: 12),
        OutlinedButton.icon(
          onPressed: _locked || _historyOpen || _petId == null
              ? null
              : _openHistory,
          icon: const Icon(Icons.history_rounded),
          label: const Text('Assessment history'),
        ),

        _assessmentStatus(),
        const SizedBox(height: 24),
      ],
    );
  }
}