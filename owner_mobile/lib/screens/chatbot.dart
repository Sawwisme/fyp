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

import '../services/cart_service.dart';
import 'chat_product_card.dart';
import 'clinic_picker.dart';
import 'book_appointment.dart';
import 'chat_booking_flow.dart';
import 'chat_product_preferences.dart';

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
  final Set<int> _bookingChatIds = {};
  final Map<int, int?> _bookingPetIds = {};
  final Map<int, GlobalKey<ChatBookingFlowState>> _bookingKeys = {};

  final _scaffoldKey = GlobalKey<ScaffoldState>();
  final _chatSearch = TextEditingController();

  bool _sidebarVisible = true;
  final _input = TextEditingController();
  final _scroll = ScrollController();

  List<Map<String, dynamic>> _chats = [];
  List<Map<String, dynamic>> _messages = [];

  Map<String, dynamic>? _selected;
  PendingChatMessage? _pending;
  String? _sidebarCommandDraft;

  int? _olderCursor;
  bool _busy = false;
  bool _hasOlder = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _initialiseChat();
  }

  @override
  void dispose() {
    _input.dispose();
    _scroll.dispose();
    super.dispose();
    _chatSearch.dispose();
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
        if (conversation['status'] == 'active' &&
            conversation['booking_draft'] is Map) {
          _bookingChatIds.add(id);
          _bookingPetIds[id] = conversation['pet_id'] as int?;
        }
        _messages = _messageItems(page);
        _hasOlder = page['has_more'] == true;
        _olderCursor = page['next_before_message_id'] as int?;
        _input.clear();
      });
      _scrollToLatest();
    });
  }

  Future<void> _initialiseChat() async {
    await _loadChats();

    if (!mounted || _error != null || _selected != null) {
      return;
    }

    // Resume an existing general chat instead of creating one
    // every time the chatbot opens.
    for (final chat in _chats) {
      if (chat['pet_id'] == null && chat['status'] == 'active') {
        await _openChat(chat);
        return;
      }
    }

    await _newGeneralChat();
  }

  Future<void> _newGeneralChat() async {
    if (_busy || _pending != null) return;

    await _run(() async {
      final chat = await widget.service.createConversation();

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

  Widget _welcome() {
    final enabled = !_busy &&
        _pending == null &&
        _selected?['status'] == 'active';

    return Padding(
      padding: const EdgeInsets.symmetric(
        vertical: 28,
        horizontal: 12,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(
            Icons.chat_bubble_outline_rounded,
            size: 36,
            color: _blue,
          ),
          const SizedBox(height: 16),
          const Text(
            'Hi! How can I help?',
            style: TextStyle(
              fontSize: 24,
              fontWeight: FontWeight.w700,
              color: _navy,
            ),
          ),
          const SizedBox(height: 10),
          const Text(
            'Ask a general dental question or get help using VetDental. '
                'Select a pet only when you want to discuss its records.',
          ),
          const SizedBox(height: 20),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              for (final question in [
                'What is gingivitis?',
                'How do I book an appointment?',
                'How often should I brush my pet’s teeth?',
              ])
                ActionChip(
                  label: Text(question),
                  onPressed: enabled
                      ? () => _askSuggested(question)
                      : null,
                ),
            ],
          ),
        ],
      ),
    );
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

  Future<void> _recommendWithPreferences() async {
    if (_busy || _pending != null || _selected == null) return;

    final conversationId = _selected!['conversation_id'] as int;

    if (_selected!['status'] != 'active' ||
        _bookingChatIds.contains(conversationId)) {
      return;
    }

    if (_selected!['pet_id'] == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Select a pet before requesting recommendations.'),
        ),
      );
      return;
    }

    final preferences = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (_) => ChatProductPreferences(
        service: ShopService(widget.service.api),
        language: _chatReplyLanguage,
      ),
    );

    if (!mounted ||
        preferences == null ||
        _busy ||
        _pending != null ||
        _selected?['conversation_id'] != conversationId ||
        _selected?['status'] != 'active') {
      return;
    }

    _sidebarCommandDraft = _input.text;
    _pending = PendingChatMessage(
      'recommend dental care products',
      productPreferences: preferences,
    );

    await _send();
  }

  Future<void> _send() async {
    if (_busy || _selected == null) return;
    if (_pending == null && _input.text.trim().isEmpty) return;

    if (_pending == null) {
      final conversationId = _selected!['conversation_id'] as int;
      final booking = _bookingKeys[conversationId]?.currentState;

      if (booking != null) {
        final originalText = _input.text;
        var handled = false;
        var completed = false;

        await _run(() async {
          handled = await booking.handleTypedInput(originalText);
          completed = true;

          if (handled &&
              mounted &&
              _selected?['conversation_id'] == conversationId &&
              _input.text == originalText) {
            _input.clear();
          }
        });

        if (!completed || handled) return;
      }
    }

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
          final savedDraft = _sidebarCommandDraft;
          if (savedDraft != null) {
            _input.text = savedDraft;
            _sidebarCommandDraft = null;
          } else {
            _input.clear();
          }
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
    if (mounted && _pending == null) {
      _sidebarCommandDraft = null;
    }
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
      case 'SELECT_PET':
        if (_selected?['status'] != 'active') return;

        if (_input.text.trim().isNotEmpty) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Send or clear your draft first.'),
            ),
          );
          return;
        }

        await _newChat();
        return;

      case 'OPEN_APPOINTMENT_BOOKING':
        final conversationId = _selected?['conversation_id'];

        if (conversationId is! int) return;

        setState(() {
          _bookingChatIds.add(conversationId);
          _bookingPetIds[conversationId] =
          _selected?['pet_id'] as int?;
        });

        _scrollToLatest();
        return;

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

    if (!mounted) return;
    await Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => page,
      ),
    );
  }

  Future<void> _openRegularBookingPage() async {
    if (_busy || _pending != null) return;

    final api = widget.service.api;

    final clinic = await Navigator.of(context)
        .push<Map<String, dynamic>>(
      MaterialPageRoute(
        builder: (_) => ClinicPickerScreen(
          service: AppointmentService(api),
        ),
      ),
    );

    if (!mounted || clinic == null) return;

    await Navigator.of(context).push<bool>(
      MaterialPageRoute(
        builder: (_) => BookAppointmentScreen(
          clinic: clinic,
          service: AppointmentService(api),
          petService: PetService(api),
          initialPetId: _selected?['pet_id'] as int?,
        ),
      ),
    );
  }

  String _suggestionLabel(String question, dynamic metadata) {
    final language = metadata is Map ? metadata['language'] : 'en';

    final index = switch (language) {
      'ms' => 0,
      'zh' => 1,
      _ => -1,
    };

    if (index == -1) return question;

    const labels = <String, List<String>>{
      'what is dental plaque': [
        'Apakah plak gigi?',
        '什么是牙菌斑？',
      ],
      'what is calculus': [
        'Apakah karang gigi?',
        '什么是牙结石？',
      ],
      'what is gingivitis': [
        'Apakah gingivitis?',
        '什么是牙龈炎？',
      ],
      'is the ai scan a diagnosis': [
        'Adakah imbasan AI merupakan diagnosis?',
        'AI 扫描属于诊断吗？',
      ],
      'how do i request a vet review': [
        'Bagaimanakah saya meminta semakan veterinar?',
        '如何申请兽医审核？',
      ],
      'how do i book an appointment': [
        'Bagaimanakah saya membuat janji temu?',
        '如何预约？',
      ],
      'how do i cancel an appointment': [
        'Bagaimanakah saya membatalkan janji temu?',
        '如何取消预约？',
      ],
      'how do i send follow up photos': [
        'Bagaimanakah saya menghantar foto susulan?',
        '如何提交随访照片？',
      ],
      'explain my latest result': [
        'Terangkan keputusan terkini saya',
        '解释最新的评估结果',
      ],
      'how severe is my pet condition': [
        'Apakah anggaran tahap keterukan haiwan saya?',
        '宠物的估计严重程度是多少？',
      ],
      'show my pet previous results': [
        'Tunjukkan keputusan terdahulu haiwan saya',
        '查看宠物以前的评估结果',
      ],
      'has my pet improved': [
        'Bandingkan keputusan penilaian haiwan saya',
        '比较宠物的评估结果',
      ],
      'what does the heatmap mean': [
        'Apakah maksud peta haba?',
        '热力图代表什么？',
      ],
      'what does segmentation mean': [
        'Apakah maksud segmentasi?',
        '什么是图像分割？',
      ],
      'what is classification confidence': [
        'Apakah skor keyakinan pengelasan?',
        '什么是分类置信分数？',
      ],
      'do i have an appointment': [
        'Adakah saya mempunyai janji temu?',
        '我有预约吗？',
      ],
      'show my pet follow up instructions': [
        'Tunjukkan arahan susulan haiwan saya',
        '查看宠物的随访说明',
      ],
      'what should i do next': [
        'Apakah langkah seterusnya?',
        '下一步应该怎么做？',
      ],
      'recommend dental care products': [
        'Cadangkan produk penjagaan gigi',
        '推荐牙齿护理产品',
      ],
      'how often should i brush my dog teeth': [
        'Berapa kerap gigi anjing perlu diberus?',
        '多久应给狗刷一次牙？',
      ],
      'how do i clean my cat teeth': [
        'Bagaimanakah saya membersihkan gigi kucing?',
        '如何清洁猫的牙齿？',
      ],
      'is bad breath normal': [
        'Adakah nafas berbau normal?',
        '口臭正常吗？',
      ],
      'what are signs of dental problems': [
        'Apakah tanda masalah pergigian?',
        '牙齿问题有哪些表现？',
      ],
      'show my pet medical history': [
        'Tunjukkan sejarah perubatan haiwan saya',
        '查看宠物的医疗历史',
      ],
      'show my pet recorded prescriptions': [
        'Tunjukkan preskripsi haiwan saya',
        '查看宠物已记录的处方',
      ],
      'show my pet segmentation percentages': [
        'Tunjukkan peratusan segmentasi haiwan saya',
        '查看宠物的图像分割百分比',
      ],
      'show my pet classification scores': [
        'Tunjukkan skor pengelasan haiwan saya',
        '查看宠物的分类分数',
      ],
    };

    final key = question.trim().toLowerCase();
    return labels[key]?[index] ?? question;
  }

  Widget _messageBubble(Map<String, dynamic> message) {
    final mine = message['sender_type'] == 'user';
    final metadata = message['response_metadata'];
    final rawSuggestions =
    metadata is Map ? metadata['suggested_questions'] : null;

    final suggestions = rawSuggestions is List
        ? rawSuggestions
        .whereType<String>()
        .where((text) => text.trim().isNotEmpty)
        .take(2)
        .toList()
        : <String>[];

    final isLatestMessage = _messages.isNotEmpty &&
        _messages.last['message_id'] == message['message_id'];

    final canChooseSuggestion = !_busy &&
        _pending == null &&
        _selected?['status'] == 'active';

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
      'OPEN_APPOINTMENT_BOOKING': 'Book with assistant',
      'SELECT_PET': 'Select pet',
    };
    final rawSources = metadata is Map ? metadata['sources'] : null;
    final rawProducts = metadata is Map ? metadata['products'] : null;

    final products = rawProducts is List
        ? rawProducts
        .whereType<Map>()
        .map((item) => Map<String, dynamic>.from(item))
        .where(
          (item) =>
      item['product_id'] is int &&
          item['clinic_id'] is int,
    )
        .take(6)
        .toList()
        : <Map<String, dynamic>>[];


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
            if (!mine) ...[
              const Text(
                'VetDental assistant',
                style: TextStyle(
                  color: _blue,
                  fontSize: 12,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 7),
            ],
            SelectableText(
              message['message_text'] as String? ?? '',
              style: TextStyle(
                color: mine ? Colors.white : _navy,
                height: 1.5,
              ),
            ),
            if (!mine && isLatestMessage && suggestions.isNotEmpty) ...[
              const SizedBox(height: 12),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  for (final question in suggestions)
                    ActionChip(
                      avatar: const Icon(
                        Icons.chat_bubble_outline_rounded,
                        size: 16,
                        color: _blue,
                      ),
                      label: Text(
                        _suggestionLabel(question, metadata),
                        style: const TextStyle(
                          color: _blue,
                          fontSize: 12,
                        ),
                      ),
                      backgroundColor: const Color(0xFFEDF2FF),
                      side: const BorderSide(
                        color: Color(0xFFD5DFFF),
                      ),
                      onPressed: canChooseSuggestion
                          ? () {
                        if (_input.text.trim().isNotEmpty) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(
                              content: Text(
                                'Send or clear your draft first.',
                              ),
                            ),
                          );
                          return;
                        }

                        _askSuggested(question);
                      }
                          : null,
                    ),
                ],
              ),
            ],
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
            if (!mine)
              for (final product in products)
                ChatProductCard(
                  key: ValueKey(
                    '${message['message_id']}:${product['clinic_id']}:'
                        '${product['product_id']}',
                  ),
                  service: CartService(widget.service.api),
                  product: product,
                  enabled: !_busy && _pending == null,
                  language: metadata is Map &&
                      {'en', 'ms', 'zh'}.contains(metadata['language'])
                      ? metadata['language'] as String
                      : 'en',
                ),
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

  String _chatTitle(Map<String, dynamic> chat) {
    final id = chat['conversation_id'];

    return chat['pet_id'] == null
        ? 'General chat #$id'
        : '${chat['pet_name'] ?? 'Pet'} · Chat #$id';
  }

  String _chatDate(Map<String, dynamic> chat) {
    final date = DateTime.tryParse('${chat['started_at']}');

    if (date == null) return '';

    final myt = date.toUtc().add(const Duration(hours: 8));

    return '${myt.day}/${myt.month}/${myt.year}'
        '${chat['status'] == 'closed' ? ' · Closed' : ''}';
  }

  Future<void> _sidebarAction(
      Future<void> Function() action,
      ) async {
    if (_busy || _pending != null) return;

    _scaffoldKey.currentState?.closeDrawer();

    await action();
  }


  String get _chatReplyLanguage {
    for (final message in _messages.reversed) {
      if (message['sender_type'] != 'assistant') continue;
      final metadata = message['response_metadata'];
      final language = metadata is Map ? metadata['language'] : null;
      return {'en', 'ms', 'zh'}.contains(language)
          ? language as String
          : 'en';
    }
    return 'en';
  }

  String get _chatReplyLanguageLabel => const {
    'en': 'English',
    'ms': 'Bahasa Melayu',
    'zh': '中文',
  }[_chatReplyLanguage]!;

  bool get _canChangeChatSettings =>
      !_busy && _pending == null && _selected?['status'] == 'active';

  Future<void> _sendSidebarCommand(String command) async {
    if (!_canChangeChatSettings) return;
    // Settings reuse normal message IDs and retry handling. The user's
    // unsent draft is retained while the command is confirmed.
    _sidebarCommandDraft = _input.text;
    _pending = PendingChatMessage(command);
    await _send();
  }

  Future<void> _showLanguageSettings() async {
    if (!_canChangeChatSettings) return;
    final currentLanguage = _chatReplyLanguage;
    final language = await showDialog<String>(
      context: context,
      builder: (dialogContext) => SimpleDialog(
        title: const Text('Reply language'),
        children: [
          const Padding(
            padding: EdgeInsets.fromLTRB(24, 0, 24, 12),
            child: Text(
              'Applies to this conversation. Mixed-language questions may '
              'select another reply language. Some replies still use English.',
            ),
          ),
          for (final option in const {
            'en': 'English',
            'ms': 'Bahasa Melayu',
            'zh': '中文',
          }.entries)
            SimpleDialogOption(
              onPressed: () => Navigator.pop(dialogContext, option.key),
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 8),
                child: Row(
                  children: [
                    Icon(
                      currentLanguage == option.key
                          ? Icons.check_circle_rounded
                          : Icons.circle_outlined,
                      color: _blue,
                    ),
                    const SizedBox(width: 12),
                    Text(option.value),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
    if (!mounted || language == null || language == currentLanguage) return;
    final command = const {
      'en': 'reply in english',
      'ms': 'reply in malay',
      'zh': 'reply in chinese',
    }[language];
    if (command != null) await _sendSidebarCommand(command);
  }

  Future<void> _showMemorySettings() async {
    if (!_canChangeChatSettings) return;
    final petName = _selected?['pet_name']?.toString();
    final reset = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Reset chat topic?'),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(petName == null ? 'General conversation' : 'Selected pet: $petName'),
              const SizedBox(height: 16),
              const Text(
                'The assistant remembers recent topics within this chat '
                'so it can understand follow-up questions. Current pet '
                'records are retrieved when needed.',
              ),
              const SizedBox(height: 12),
              const Text(
                'Resetting topic memory starts a fresh topic. Your chat '
                'history, selected pet, appointments and medical records '
                'remain saved.',
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Text('Close'),
          ),
          FilledButton.icon(
            onPressed: () => Navigator.pop(dialogContext, true),
            icon: const Icon(Icons.restart_alt_rounded),
            label: const Text('Reset topic memory'),
          ),
        ],
      ),
    );
    if (!mounted || reset != true) return;
    await _sendSidebarCommand('change topic');
  }

  Widget _sidebarSettings() {
    final enabled = _canChangeChatSettings;
    return Column(
      children: [
        const Divider(color: Colors.white12),
        ListTile(
          dense: true,
          contentPadding: const EdgeInsets.symmetric(horizontal: 8),
          leading: const Icon(Icons.language_rounded, color: Colors.white70),
          title: const Text('Language', style: TextStyle(color: Colors.white)),
          subtitle: Text(
            _chatReplyLanguageLabel,
            style: const TextStyle(color: Colors.white54),
          ),
          enabled: enabled,
          onTap: enabled ? () => _sidebarAction(_showLanguageSettings) : null,
        ),
        ListTile(
          dense: true,
          contentPadding: const EdgeInsets.symmetric(horizontal: 8),
          leading: const Icon(Icons.psychology_outlined, color: Colors.white70),
          title: const Text(
            'Reset chat topic',
            style: TextStyle(color: Colors.white),
          ),
          subtitle: const Text(
            'Start fresh without deleting messages',
            style: TextStyle(color: Colors.white54),
          ),
          enabled: enabled,
          onTap: enabled ? () => _sidebarAction(_showMemorySettings) : null,
        ),
      ],
    );
  }

  Widget _chatSidebar() {
    final query = _chatSearch.text.trim().toLowerCase();

    final visible = _chats
        .where(
          (chat) => _chatTitle(chat).toLowerCase().contains(query),
    )
        .toList();

    final disabled = _busy || _pending != null;

    return ColoredBox(
      color: _navy,
      child: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                children: [
                  const Expanded(
                    child: Text(
                      'Your conversations',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 18,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                  IconButton(
                    tooltip: 'Close chat history',
                    icon: const Icon(
                      Icons.close_rounded,
                      color: Colors.white70,
                    ),
                    onPressed: () {
                      final scaffold = _scaffoldKey.currentState;

                      if (scaffold?.isDrawerOpen ?? false) {
                        scaffold?.closeDrawer();
                      } else {
                        setState(() => _sidebarVisible = false);
                      }
                    },
                  ),
                ],
              ),
              const SizedBox(height: 20),
              Tooltip(
                message: 'New general chat',
                child: FilledButton.icon(
                  onPressed: disabled
                      ? null
                      : () => _sidebarAction(_newGeneralChat),
                  icon: const Icon(Icons.add),
                  label: const Text('New chat'),
                  style: FilledButton.styleFrom(
                    backgroundColor: _blue,
                    foregroundColor: Colors.white,
                    minimumSize: const Size.fromHeight(46),
                  ),
                ),
              ),
              const SizedBox(height: 8),
              TextButton.icon(
                onPressed: disabled
                    ? null
                    : () => _sidebarAction(_newChat),
                icon: const Icon(
                  Icons.pets_outlined,
                  size: 18,
                ),
                label: const Text('Chat about a pet'),
                style: TextButton.styleFrom(
                  foregroundColor: Colors.white70,
                ),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _chatSearch,
                onChanged: (_) => setState(() {}),
                style: const TextStyle(color: Colors.white),
                decoration: InputDecoration(
                  hintText: 'Search chats',
                  hintStyle: const TextStyle(
                    color: Colors.white54,
                  ),
                  prefixIcon: const Icon(
                    Icons.search,
                    color: Colors.white54,
                  ),
                  filled: true,
                  fillColor: const Color(0xFF243247),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: BorderSide.none,
                  ),
                ),
              ),
              const SizedBox(height: 16),
              const Divider(color: Colors.white12),
              Expanded(
                child: visible.isEmpty
                    ? const Center(
                  child: Text(
                    'No chats found.',
                    style: TextStyle(
                      color: Colors.white54,
                    ),
                  ),
                )
                    : ListView.builder(
                  itemCount: visible.length,
                  itemBuilder: (context, index) {
                    final chat = visible[index];

                    final selected =
                        chat['conversation_id'] ==
                            _selected?['conversation_id'];

                    return Padding(
                      padding: const EdgeInsets.only(
                        bottom: 6,
                      ),
                      child: ListTile(
                        selected: selected,
                        selectedTileColor: _blue,
                        shape: RoundedRectangleBorder(
                          borderRadius:
                          BorderRadius.circular(12),
                        ),
                        leading: Icon(
                          chat['pet_id'] == null
                              ? Icons.chat_bubble_outline
                              : Icons.pets_outlined,
                          size: 19,
                          color: Colors.white70,
                        ),
                        title: Text(
                          _chatTitle(chat),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 14,
                          ),
                        ),
                        subtitle: Text(
                          _chatDate(chat),
                          style: const TextStyle(
                            color: Colors.white54,
                            fontSize: 11,
                          ),
                        ),
                        enabled: !disabled,
                        onTap: disabled
                            ? null
                            : () => _sidebarAction(
                              () => _openChat(chat),
                        ),
                      ),
                    );
                  },
                ),
              ),
              _sidebarSettings(),
              TextButton.icon(
                onPressed: disabled ? null : _loadChats,
                icon: const Icon(Icons.refresh, size: 18),
                label: const Text('Refresh history'),
                style: TextButton.styleFrom(
                  foregroundColor: Colors.white70,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _conversationBody() {
    final canSend =
        _selected != null && _selected!['status'] == 'active';

    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
          child: Row(
            children: [
              Expanded(
                child: Text(
                  _selected?['pet_id'] == null
                      ? 'General chat'
                      : 'Chat about '
                      '${_selected?['pet_name'] ?? 'your pet'}',
                  style: const TextStyle(
                    color: _navy,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
              TextButton.icon(
                onPressed: _busy || _pending != null
                    ? null
                    : _newChat,
                icon: const Icon(
                  Icons.pets_outlined,
                  size: 17,
                ),
                label: const Text('Select pet'),
              ),
            ],
          ),
        ),
        if (canSend &&
            !_bookingChatIds.contains(_selected?['conversation_id']))
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Align(
              alignment: Alignment.centerLeft,
              child: TextButton.icon(
                onPressed: _busy || _pending != null
                    ? null
                    : _recommendWithPreferences,
                icon: const Icon(Icons.tune_rounded),
                label: Text(
                  _chatReplyLanguage == 'ms'
                      ? 'Cari produk yang sesuai'
                      : _chatReplyLanguage == 'zh'
                      ? '查找合适的产品'
                      : 'Find suitable products',
                ),
              ),
            ),
          ),
        if (_busy) const LinearProgressIndicator(),
        if (_error != null)
          Padding(
            padding: const EdgeInsets.all(12),
            child: Text(
              _error!,
              style: const TextStyle(
                color: Color(0xFFB42318),
              ),
            ),
          ),
        Expanded(
          child: _selected == null
              ? Center(
            child: TextButton(
              onPressed: _busy ? null : _initialiseChat,
              child: const Text('Open chat'),
            ),
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
              if (_messages.isEmpty) _welcome(),
              ..._messages.map(_messageBubble),
              for (final conversationId in _bookingChatIds)
                Offstage(
                  key: ValueKey('booking-chat-$conversationId'),
                  offstage:
                  _selected?['conversation_id'] != conversationId,
                  child: ChatBookingFlow(
                    key: _bookingKeys.putIfAbsent(
                      conversationId,
                          () => GlobalKey<ChatBookingFlowState>(),
                    ),
                    chatbot: widget.service,
                    conversationId: conversationId,
                    initialPetId: _bookingPetIds[conversationId],
                    language: _chatReplyLanguage,
                    appointments: AppointmentService(widget.service.api),
                    pets: PetService(widget.service.api),
                    onOpenBookingPage: _openRegularBookingPage,
                    onCancel: () {
                      setState(() {
                        _bookingKeys.remove(conversationId);
                        _bookingChatIds.remove(conversationId);
                        _bookingPetIds.remove(conversationId);
                      });
                    },
                  ),
                ),
            ],
          ),
        ),
        if (_pending != null)
          Padding(
            padding: const EdgeInsets.symmetric(
              horizontal: 16,
            ),
            child: Row(
              children: [
                const Expanded(
                  child: Text(
                    'Waiting for confirmation. '
                        'Retry the same message.',
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
            padding: const EdgeInsets.fromLTRB(10, 8, 16, 8),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                IconButton(
                  tooltip: 'Suggested questions',
                  onPressed: _busy ||
                      _pending != null ||
                      !canSend
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
                    enabled:
                    !_busy && _pending == null && canSend,
                    minLines: 1,
                    maxLines: 4,
                    maxLength: 2000,
                    decoration: InputDecoration(
                      hintText: canSend
                          ? 'Message VetDental…'
                          : 'This chat is closed.',
                      filled: true,
                      fillColor: Colors.white,
                      counterText: '',
                      border: OutlineInputBorder(
                        borderRadius:
                        BorderRadius.circular(20),
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                IconButton.filled(
                  tooltip: 'Send message',
                  onPressed:
                  _busy || !canSend || _pending != null
                      ? null
                      : _send,
                  icon: const Icon(
                    Icons.arrow_upward_rounded,
                  ),
                ),
              ],
            ),
          ),
        const Padding(
          padding: EdgeInsets.only(
            left: 16,
            right: 16,
            bottom: 8,
          ),
          child: Text(
            'AI guidance does not replace veterinary care.',
            textAlign: TextAlign.center,
            style: TextStyle(
              fontSize: 11,
              color: Color(0xFF687284),
            ),
          ),
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final wide = constraints.maxWidth >= 850;

        return Scaffold(
          key: _scaffoldKey,
          backgroundColor: const Color(0xFFEEF1F5),
          drawer: wide
              ? null
              : Drawer(
            width: 290,
            child: _chatSidebar(),
          ),
          appBar: AppBar(
            automaticallyImplyLeading: false,
            backgroundColor: _navy,
            foregroundColor: Colors.white,
            leading: IconButton(
              tooltip: wide
                  ? (_sidebarVisible ? 'Hide chats' : 'Show chats')
                  : 'Chat history',
              icon: const Icon(Icons.menu_rounded),
              onPressed: () {
                if (wide) {
                  setState(() {
                    _sidebarVisible = !_sidebarVisible;
                  });
                } else {
                  _scaffoldKey.currentState?.openDrawer();
                }
              },
            ),
            title: const Text(
              'Dental assistant',
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
            actions: [
              if (Navigator.of(context).canPop())
                IconButton(
                  tooltip: 'Close assistant',
                  icon: const Icon(Icons.close_rounded),
                  onPressed: () => Navigator.of(context).maybePop(),
                ),
            ],
          ),
          body: SafeArea(
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                if (wide)
                  AnimatedContainer(
                    duration:
                    const Duration(milliseconds: 220),
                    curve: Curves.easeInOut,
                    width: _sidebarVisible ? 280 : 0,
                    child: ClipRect(
                      child: OverflowBox(
                        minWidth: 280,
                        maxWidth: 280,
                        alignment: Alignment.topLeft,
                        child: _chatSidebar(),
                      ),
                    ),
                  ),
                Expanded(
                  child: _conversationBody(),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}