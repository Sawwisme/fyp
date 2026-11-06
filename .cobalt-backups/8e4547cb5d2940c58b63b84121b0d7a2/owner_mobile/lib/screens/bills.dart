import 'package:flutter/material.dart';

import '../services/billing_service.dart';
import 'bill_details.dart';

class BillsScreen extends StatefulWidget {
  final BillingService service;

  const BillsScreen({
    super.key,
    required this.service,
  });

  @override
  State<BillsScreen> createState() => _BillsScreenState();
}

class _BillsScreenState extends State<BillsScreen> {
  static const _green = Color(0xFF176B32);
  static const _pageSize = 10;

  late Future<Map<String, dynamic>> _future;

  String? _status;
  int _page = 0;
  bool _openingBill = false;

  @override
  void initState() {
    super.initState();
    _future = _fetch();
  }

  Future<Map<String, dynamic>> _fetch() {
    return widget.service.getBills(
      status: _status,
      offset: _page * _pageSize,
      limit: _pageSize,
    );
  }

  void _reload([int? page]) {
    setState(() {
      if (page != null) _page = page;
      _future = _fetch();
    });
  }

  String _money(dynamic value) {
    final amount = num.tryParse(value?.toString() ?? '');
    return amount == null
        ? '—'
        : 'RM ${amount.toStringAsFixed(2)}';
  }

  String _date(dynamic value) {
    final parsed = DateTime.tryParse(value?.toString() ?? '');
    if (parsed == null) return '—';

    final date = parsed.toUtc().add(const Duration(hours: 8));

    return '${date.day.toString().padLeft(2, '0')}/'
        '${date.month.toString().padLeft(2, '0')}/'
        '${date.year}';
  }

  String _statusLabel(dynamic value) {
    return {
      'issued': 'Awaiting payment',
      'paid': 'Paid',
      'void': 'Void',
    }[value] ?? 'Unknown';
  }

  Widget _filter(String title, String? status) {
    return ChoiceChip(
      label: Text(title),
      selected: _status == status,
      showCheckmark: false,
      selectedColor: const Color(0xFFE1F0E5),
      onSelected: _openingBill
          ? null
          : (_) {
        if (_status == status) return;

        setState(() {
          _status = status;
          _page = 0;
          _future = _fetch();
        });
      },
    );
  }

  Future<void> _openBill(Map<String, dynamic> bill) async {
    if (_openingBill) return;

    setState(() => _openingBill = true);

    try {
      await Navigator.of(context).push<void>(
        MaterialPageRoute(
          builder: (_) => BillDetailsScreen(
            service: widget.service,
            billId: bill['consultation_bill_id'] as int,
          ),
        ),
      );
    } finally {
      if (mounted) {
        setState(() {
          _openingBill = false;
          _future = _fetch();
        });
      }
    }
  }

  Widget _card(Map<String, dynamic> bill) {
    final paid = bill['status'] == 'paid';

    return Container(
      margin: const EdgeInsets.only(bottom: 14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFFDDE7DF)),
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(14),
        onTap: _openingBill ? null : () => _openBill(bill),
        child: Padding(
          padding: const EdgeInsets.all(18),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: Text(
                      bill['pet_name'].toString(),
                      style: const TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Text(
                    _money(bill['total_amount']),
                    style: const TextStyle(
                      color: _green,
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 10),
              Text(
                bill['clinic_name'].toString(),
                style: const TextStyle(
                  fontWeight: FontWeight.w500,
                ),
              ),
              const SizedBox(height: 6),
              Text(
                'Visit: ${_date(bill['consultation_date'])}',
                style: const TextStyle(color: Colors.black54),
              ),
              Text(
                'Bill #${bill['consultation_bill_id']} · '
                    'Issued ${_date(bill['issued_at'])}',
                style: const TextStyle(
                  color: Colors.black54,
                  fontSize: 12,
                ),
              ),
              const Divider(height: 26),
              Row(
                children: [
                  Expanded(
                    child: Text(
                      _statusLabel(bill['status']),
                      style: TextStyle(
                        color: paid
                            ? _green
                            : const Color(0xFF805B00),
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                  const Text(
                    'View bill',
                    style: TextStyle(color: _green),
                  ),
                  const SizedBox(width: 6),
                  const Icon(
                    Icons.chevron_right,
                    color: _green,
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF5F7F5),
      appBar: AppBar(
        title: const Text('Bills & Receipts'),
        actions: [
          IconButton(
            tooltip: 'Refresh bills',
            onPressed: _openingBill ? null : () => _reload(),
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 12, 20, 8),
            child: Align(
              alignment: Alignment.centerLeft,
              child: Wrap(
                spacing: 8,
                runSpacing: 4,
                children: [
                  _filter('All', null),
                  _filter('Unpaid', 'issued'),
                  _filter('Paid', 'paid'),
                  _filter('Void', 'void'),
                ],
              ),
            ),
          ),
          Expanded(
            child: FutureBuilder<Map<String, dynamic>>(
              future: _future,
              builder: (context, snapshot) {
                if (snapshot.connectionState != ConnectionState.done) {
                  return const Center(
                    child: CircularProgressIndicator(),
                  );
                }

                if (snapshot.hasError) {
                  return Center(
                    child: Padding(
                      padding: const EdgeInsets.all(24),
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Text(
                            snapshot.error.toString(),
                            textAlign: TextAlign.center,
                          ),
                          const SizedBox(height: 12),
                          OutlinedButton(
                            onPressed: () => _reload(),
                            child: const Text('Try again'),
                          ),
                        ],
                      ),
                    ),
                  );
                }

                final data = snapshot.data!;
                final total = data['total'] as int;
                final items = (data['items'] as List)
                    .map(
                      (item) => Map<String, dynamic>.from(item as Map),
                )
                    .toList();

                return ListView(
                  padding: const EdgeInsets.all(20),
                  children: [
                    if (items.isEmpty)
                      const Padding(
                        padding: EdgeInsets.symmetric(vertical: 40),
                        child: Text(
                          'No bills match this filter.',
                          textAlign: TextAlign.center,
                        ),
                      ),
                    ...items.map(_card),
                    if (_page > 0 ||
                        (_page + 1) * _pageSize < total)
                      Row(
                        mainAxisAlignment:
                        MainAxisAlignment.spaceBetween,
                        children: [
                          OutlinedButton(
                            onPressed: !_openingBill && _page > 0
                                ? () => _reload(_page - 1)
                                : null,
                            child: const Text('Previous'),
                          ),
                          Text('Page ${_page + 1}'),
                          OutlinedButton(
                            onPressed: !_openingBill &&
                                (_page + 1) * _pageSize < total
                                ? () => _reload(_page + 1)
                                : null,
                            child: const Text('Next'),
                          ),
                        ],
                      ),
                  ],
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}