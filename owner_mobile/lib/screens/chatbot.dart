import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import '../services/api_client.dart';

import '../services/chatbot_service.dart';
import '../services/pet_service.dart';

import '../services/appointment_service.dart';
import '../services/dental_assessment_service.dart';
import '../services/followup_service.dart';

import 'ai_scan.dart';
import 'appointments.dart';
import 'followup_care.dart';
import '../services/shop_service.dart';
import 'shop.dart';
import 'medical_history.dart';


class ChatbotScreen extends StatefulWidget {
  final ChatbotService service;

  const ChatbotScreen({
    super.key,
    required this.service,
  });

  @override
  State<ChatbotScreen> createState() => _ChatbotScreenState();
}

class _ChatbotScreenState extends State<ChatbotScreen> {
  static const _blue = Color(0xFF2549C7);
  static const _navy = Color(0xFF172333);

  final _input = TextEditingController();
  final _scroll = ScrollController();

  List<Map<String, dynamic>> _chats = [];
  List<Map<String, dynamic>> _messages = [];

  Map<String, dynamic>? _selected;
  PendingChatMessage? _pending;

  int? _olderCursor;
  bool _busy = false;
  bool _hasOlder = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadChats();
  }

  @override
  void dispose() {
    _input.dispose();
    _scroll.dispose();
    super.dispose();
  }

  List<Map<String, dynamic>> _messageItems(
      Map<String, dynamic> page,
      ) {
    return (page['items'] as List)
        .map((item) => Map<String, dynamic>.from(item as Map))
        .toList();
  }

  Future<void> _run(Future<void> Function() action) async {
    if (_busy) return;

    setState(() {
      _busy = true;
      _error = null;
    });

    try {
      await action();
    } catch (error) {
      if (mounted) {
        setState(() => _error = error.toString());
      }
    } finally {
      if (mounted) {
        setState(() => _busy = false);
      }
    }
  }

  Future<void> _loadChats() async {
    await _run(() async {
      final byId = <int, Map<String, dynamic>>{};
      var offset = 0;

      while (true) {
        final page = await widget.service.listConversations(
          offset: offset,
          limit: 100,
        );

        if (!mounted) return;

        for (final chat in page) {
          byId.putIfAbsent(
            chat['conversation_id'] as int,
                () => chat,
          );
        }

        if (page.length < 100) break;
        offset += page.length;
      }

      if (!mounted) return;

      setState(() {
        final selected = _selected;

        _chats = [
          if (selected != null &&
              !byId.containsKey(selected['conversation_id']))
            selected,
          ...byId.values,
        ];
      });
    });
  }

  Future<void> _openChat(Map<String, dynamic> chat) async {
    if (_pending != null) return;

    await _run(() async {
      final id = chat['conversation_id'] as int;
      final conversation = await widget.service.getConversation(id);
      final page = await widget.service.listMessages(id);

      if (!mounted) return;

      setState(() {
        _selected = conversation;
        _messages = _messageItems(page);
        _hasOlder = page['has_more'] == true;
        _olderCursor = page['next_before_message_id'] as int?;
        _input.clear();
      });
      _scrollToLatest();
    });
  }

  Future<void> _newChat() async {
    if (_busy || _pending != null) return;

    await _run(() async {
      final petService = PetService(widget.service.api);
      final pets = <Map<String, dynamic>>[];

      // Load every page so owners with many pets can select any pet.
      var offset = 0;

      while (true) {
        final page = await petService.getPets(
          offset: offset,
          limit: 100,
        );

        pets.addAll(page);

        if (page.length < 100) break;
        offset += page.length;
      }

      if (!mounted) return;

      // null = dismissed, 0 = general chat, positive ID = selected pet.
      final selection = await showDialog<int>(
        context: context,
        builder: (dialogContext) {
          return SimpleDialog(
            title: const Text('Who is this chat about?'),
            children: [
              SimpleDialogOption(
                onPressed: () {
                  Navigator.of(dialogContext).pop(0);
                },
                child: const Padding(
                  padding: EdgeInsets.symmetric(vertical: 8),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'General dental questions',
                        style: TextStyle(fontWeight: FontWeight.w700),
                      ),
                      SizedBox(height: 4),
                      Text('No pet records will be used.'),
                    ],
                  ),
                ),
              ),
              if (pets.isNotEmpty) const Divider(),
              for (final pet in pets)
                SimpleDialogOption(
                  onPressed: () {
                    Navigator.of(dialogContext).pop(
                      pet['pet_id'] as int,
                    );
                  },
                  child: Padding(
                    padding: const EdgeInsets.symmetric(vertical: 8),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          pet['pet_name'] as String? ?? 'Pet',
                          style: const TextStyle(
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          [
                            pet['species'],
                            pet['breed'],
                          ]
                              .whereType<String>()
                              .where((value) => value.trim().isNotEmpty)
                              .join(' · '),
                        ),
                      ],
                    ),
                  ),
                ),
              if (pets.isEmpty)
                const Padding(
                  padding: EdgeInsets.all(24),
                  child: Text(
                    'Add a pet in My Pets to ask about its '
                        'assessment results.',
                  ),
                ),
            ],
          );
        },
      );

      if (!mounted || selection == null) return;

      final chat = await widget.service.createConversation(
        petId: selection == 0 ? null : selection,
      );

      if (!mounted) return;

      setState(() {
        _selected = chat;
        _chats = [
          chat,
          ..._chats.where(
                (item) =>
            item['conversation_id'] != chat['conversation_id'],
          ),
        ];
        _messages = [];
        _hasOlder = false;
        _olderCursor = null;
        _input.clear();
      });
    });
  }

  Future<void> _loadOlder() async {
    if (_selected == null || _olderCursor == null) return;

    await _run(() async {
      final page = await widget.service.listMessages(
        _selected!['conversation_id'] as int,
        beforeMessageId: _olderCursor,
      );

      if (!mounted) return;

      setState(() {
        _messages = [..._messageItems(page), ..._messages];
        _hasOlder = page['has_more'] == true;
        _olderCursor = page['next_before_message_id'] as int?;
      });
    });
  }

  void _scrollToLatest() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted || !_scroll.hasClients) return;

      _scroll.animateTo(
        _scroll.position.maxScrollExtent,
        duration: const Duration(milliseconds: 250),
        curve: Curves.easeOut,
      );
    });
  }

  Future<void> _showQuestions() async {
    if (_busy || _pending != null || _selected == null) return;
    if (_selected!['status'] != 'active') return;

    FocusScope.of(context).unfocus();

    final questions = <String>[
      if (_selected!['pet_id'] != null) ...[
        'Explain my latest result',
        'How severe is my pet condition',
        'What should I do next',
        'Compare with the previous result',
        'When is my next appointment',
        'Show my pet follow up instructions',
        'Show my pet medical history',
        'Show my pet recorded prescriptions',
        'Show my pet segmentation percentages',
        'Show my pet classification scores',
      ],
      'Recommend dental care products',
      'What does the heatmap mean',
      'What does segmentation mean',
      'What is classification confidence',
      'How do I brush pet teeth',
      'What are signs of dental problems',
    ];

    final question = await showModalBottomSheet<String>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (sheetContext) {
        return SafeArea(
          child: SizedBox(
            height: MediaQuery.sizeOf(sheetContext).height * 0.7,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Padding(
                  padding: EdgeInsets.fromLTRB(20, 4, 20, 16),
                  child: Text(
                    'Suggested questions',
                    style: TextStyle(
                      fontSize: 21,
                      fontWeight: FontWeight.w700,
                      color: _navy,
                    ),
                  ),
                ),
                Expanded(
                  child: ListView.separated(
                    itemCount: questions.length,
                    separatorBuilder: (_, _) => const Divider(height: 1),
                    itemBuilder: (_, index) {
                      final text = questions[index];

                      return ListTile(
                        contentPadding: const EdgeInsets.symmetric(
                          horizontal: 20,
                          vertical: 4,
                        ),
                        title: Text(text),
                        trailing: const Icon(
                          Icons.arrow_forward_rounded,
                          size: 18,
                          color: _blue,
                        ),
                        onTap: () {
                          Navigator.of(sheetContext).pop(text);
                        },
                      );
                    },
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );

    if (!mounted || question == null) return;

    _askSuggested(question);
  }

  void _askSuggested(String question) {
    if (_busy ||
        _pending != null ||
        _selected == null ||
        _selected!['status'] != 'active') {
      return;
    }

    _input.text = question;
    _send();
  }

  Future<void> _send() async {
    if (_busy || _selected == null) return;
    if (_pending == null && _input.text.trim().isEmpty) return;

    await _run(() async {
      final conversationId = _selected!['conversation_id'] as int;

      _pending ??= PendingChatMessage(_input.text);

      try {
        final result = await widget.service.sendMessage(
          conversationId,
          _pending!,
        );

        final returned = (result['messages'] as List)
            .map((item) => Map<String, dynamic>.from(item as Map))
            .toList();

        if (!mounted) return;

        setState(() {
          final byId = <int, Map<String, dynamic>>{
            for (final message in [..._messages, ...returned])
              message['message_id'] as int: message,
          };

          _messages = byId.values.toList()
            ..sort(
                  (a, b) => (a['message_id'] as int)
                  .compareTo(b['message_id'] as int),
            );

          _pending = null;
          _input.clear();
        });

        _scrollToLatest();
      } on ApiException catch (error) {
        if (!mounted) rethrow;

        // These responses reject the request before saving a pair.
        if ({400, 401, 403, 404, 422}.contains(error.statusCode)) {
          setState(() => _pending = null);
        } else if (error.statusCode == 409) {
          try {
            final conversation = await widget.service.getConversation(
              conversationId,
            );

            if (mounted && conversation['status'] == 'closed') {
              setState(() {
                _selected = conversation;
                _pending = null;
              });
            }
          } on ApiException {
            // If verification fails, retain the original request ID.
          }
        }

        // Timeouts and uncertain failures retain _pending for safe retry.
        rethrow;
      }
    });
  }

  Future<void> _openSource(String source) async {
    final uri = Uri.tryParse(source);

    if (uri == null ||
        uri.scheme != 'https' ||
        uri.host.isEmpty) {
      return;
    }

    try {
      final opened = await launchUrl(
        uri,
        mode: LaunchMode.externalApplication,
      );

      if (!opened && mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Cannot open this source.')),
        );
      }
    } catch (_) {
      if (!mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Cannot open this source.')),
      );
    }
  }

  Future<void> _openChatAction(
      String action, {
        Map<String, dynamic>? reference,
      }) async {
    if (_busy || _pending != null) return;

    final api = widget.service.api;

    late Widget page;

    switch (action) {
      case 'OPEN_AI_ANALYSIS':
        page = Scaffold(
          appBar: AppBar(
            title: const Text('AI dental assessment'),
            backgroundColor: _navy,
            foregroundColor: Colors.white,
          ),
          body: AiScanPage(
            petService: PetService(api),
            service: DentalAssessmentService(api),
            initialPetId: reference?['pet_id'] is int
                ? reference!['pet_id'] as int
                : _selected?['pet_id'] as int?,
            initialAssessmentJobId:
            reference?['assessment_job_id'] is int
                ? reference!['assessment_job_id'] as int
                : null,
          ),
        );
        break;

      case 'OPEN_APPOINTMENTS':
        page = Scaffold(
          appBar: AppBar(
            title: const Text('Appointments'),
            backgroundColor: _navy,
            foregroundColor: Colors.white,
          ),
          body: AppointmentsPage(
            service: AppointmentService(api),
            petService: PetService(api),
          ),
        );
        break;

      case 'OPEN_FOLLOWUP_CARE':
        page = FollowupCareScreen(
          service: FollowupService(api),
        );
        break;

      case 'OPEN_SHOP':
        page = Scaffold(
          appBar: AppBar(
            title: const Text('Dental care shop'),
            backgroundColor: _navy,
            foregroundColor: Colors.white,
          ),
          body: ShopScreen(
            service: ShopService(api),
          ),
        );
        break;

      case 'OPEN_MEDICAL_HISTORY':
        final petId = _selected?['pet_id'];

        if (petId is! int) return;

        page = MedicalHistoryScreen(
          petId: petId,
          petName: _selected?['pet_name'] as String? ?? 'Your pet',
          service: PetService(api),
        );
        break;

      default:
        return;
    }

    await Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => page,
      ),
    );
  }

  Widget _messageBubble(Map<String, dynamic> message) {
    final mine = message['sender_type'] == 'user';
    final metadata = message['response_metadata'];

    final rawReference = metadata is Map
        ? metadata['context_reference']
        : null;

    final reference = rawReference is Map
        ? Map<String, dynamic>.from(rawReference)
        : <String, dynamic>{};

    final action = metadata is Map
        ? metadata['recommended_action']
        : null;

    const actionLabels = {
      'OPEN_AI_ANALYSIS': 'Open AI Scan',
      'OPEN_APPOINTMENTS': 'Open appointments',
      'OPEN_FOLLOWUP_CARE': 'Open follow-up care',
      'OPEN_SHOP': 'Browse clinic shops',
      'OPEN_MEDICAL_HISTORY': 'Open medical history',
    };
    final rawSources = metadata is Map ? metadata['sources'] : null;

    final sources = rawSources is List
        ? rawSources.whereType<String>().toList()
        : <String>[];

    return Align(
      alignment: mine ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        constraints: const BoxConstraints(maxWidth: 560),
        margin: const EdgeInsets.only(bottom: 14),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: mine ? _blue : Colors.white,
          borderRadius: BorderRadius.circular(18),
          border: mine
              ? null
              : Border.all(color: const Color(0xFFDCE2ED)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              mine ? 'You' : 'VetDental assistant',
              style: TextStyle(
                color: mine ? Colors.white70 : _blue,
                fontSize: 12,
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 7),
            SelectableText(
              message['message_text'] as String? ?? '',
              style: TextStyle(
                color: mine ? Colors.white : _navy,
                height: 1.5,
              ),
            ),
            if (!mine &&
                action is String &&
                actionLabels.containsKey(action)) ...[
              const SizedBox(height: 12),
              OutlinedButton.icon(
                onPressed: _busy || _pending != null
                    ? null
                    : () => _openChatAction(
                  action,
                  reference: reference,
                ),
                icon: const Icon(Icons.arrow_forward_rounded, size: 18),
                label: Text(actionLabels[action]!),
              ),
            ],
            for (final source in sources)
              TextButton.icon(
                onPressed: () => _openSource(source),
                icon: const Icon(Icons.open_in_new, size: 15),
                label: Text(
                  Uri.tryParse(source)?.host ?? 'Read source',
                ),
              ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final canSend =
        _selected != null && _selected!['status'] == 'active';

    return Scaffold(
      backgroundColor: const Color(0xFFEEF1F5),
      appBar: AppBar(
        title: const Text('Dental care assistant'),
        backgroundColor: _navy,
        foregroundColor: Colors.white,
        actions: [
          IconButton(
            tooltip: 'Refresh recent chats',
            onPressed: _busy || _pending != null ? null : _loadChats,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: SafeArea(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                children: [
                  const Text(
                    'Dental information and app guidance. '
                        'For diagnosis or treatment, contact your veterinarian.',
                    style: TextStyle(
                      color: Color(0xFF52647C),
                      height: 1.4,
                    ),
                  ),
                  const SizedBox(height: 14),
                  Row(
                    children: [
                      Expanded(
                        child: DropdownButtonFormField<int>(
                          key: ValueKey(_selected?['conversation_id']),
                          initialValue:
                          _selected?['conversation_id'] as int?,
                          isExpanded: true,
                          decoration: const InputDecoration(
                            labelText: 'Your chats',
                            filled: true,
                            fillColor: Colors.white,
                            border: OutlineInputBorder(),
                          ),
                          items: _chats.map((chat) {
                            final id = chat['conversation_id'] as int;

                            return DropdownMenuItem<int>(
                              value: id,
                              child: Text(
                                'Chat #$id'
                                    '${chat['pet_name'] == null ? '' : ' · ${chat['pet_name']}'}',
                                overflow: TextOverflow.ellipsis,
                              ),
                            );
                          }).toList(),
                          onChanged: _busy || _pending != null
                              ? null
                              : (id) {
                            if (id == null) return;
                            _openChat(
                              _chats.firstWhere(
                                    (chat) =>
                                chat['conversation_id'] == id,
                              ),
                            );
                          },
                        ),
                      ),
                      const SizedBox(width: 10),
                      IconButton.filled(
                        tooltip: 'New chat',
                        onPressed:
                        _busy || _pending != null ? null : _newChat,
                        icon: const Icon(Icons.add),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            if (_selected != null)
              Container(
                width: double.infinity,
                margin: const EdgeInsets.fromLTRB(16, 0, 16, 12),
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: const Color(0xFFE3E9FF),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  _selected!['pet_id'] == null
                      ? 'General chat · No pet records used'
                      : 'Chat about ${_selected!['pet_name'] ?? 'your pet'}'
                      ' · Start a new chat to choose another pet',
                  style: const TextStyle(
                    color: _navy,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            if (_busy) const LinearProgressIndicator(),
            if (_error != null)
              Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: 16,
                  vertical: 8,
                ),
                child: Text(
                  _error!,
                  style: const TextStyle(color: Color(0xFFB42318)),
                ),
              ),
            Expanded(
              child: _selected == null
                  ? const Center(
                child: Text('Select a recent chat or tap + to begin.'),
              )
                  : ListView(
                controller: _scroll,
                padding: const EdgeInsets.all(16),
                children: [
                  if (_hasOlder)
                    TextButton(
                      onPressed: _busy ? null : _loadOlder,
                      child: const Text('Load older messages'),
                    ),
                  if (_messages.isEmpty)
                    const Padding(
                      padding: EdgeInsets.all(24),
                      child: Text(
                        'Ask about plaque, tartar, gum inflammation, '
                            'booking or follow-up care.',
                        textAlign: TextAlign.center,
                      ),
                    ),
                  ..._messages.map(_messageBubble),
                ],
              ),
            ),
            if (_pending != null)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: Row(
                  children: [
                    const Expanded(
                      child: Text(
                        'Waiting for confirmation. Retry the same message.',
                      ),
                    ),
                    TextButton(
                      onPressed: _busy ? null : _send,
                      child: const Text('Retry'),
                    ),
                  ],
                ),
              ),
            if (_selected != null)
              Padding(
                padding: const EdgeInsets.all(16),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    IconButton(
                      tooltip: 'Suggested questions',
                      onPressed: _busy || _pending != null || !canSend
                          ? null
                          : _showQuestions,
                      icon: const Icon(
                        Icons.lightbulb_outline_rounded,
                        color: _blue,
                      ),
                    ),
                    Expanded(
                      child: TextField(
                        controller: _input,
                        enabled: !_busy && _pending == null && canSend,
                        minLines: 1,
                        maxLines: 4,
                        maxLength: 2000,
                        decoration: InputDecoration(
                          hintText: canSend
                              ? 'Ask a question…'
                              : 'This chat is closed.',
                          filled: true,
                          fillColor: Colors.white,
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(16),
                          ),
                          counterText: '',
                        ),
                      ),
                    ),
                    const SizedBox(width: 10),
                    IconButton.filled(
                      tooltip: 'Send message',
                      onPressed: _busy || !canSend || _pending != null
                          ? null
                          : _send,
                      icon: const Icon(Icons.send_rounded),
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