import 'package:flutter/material.dart';

import '../services/billing_service.dart';

class BillDetailsScreen extends StatefulWidget {
  final BillingService service;
  final int billId;

  const BillDetailsScreen({
    super.key,
    required this.service,
    required this.billId,
  });

  @override
  State<BillDetailsScreen> createState() =>
      _BillDetailsScreenState();
}

class _BillDetailsScreenState extends State<BillDetailsScreen> {
  static const _green = Color(0xFF176B32);

  late Future<Map<String, dynamic>> _future;

  @override
  void initState() {
    super.initState();
    _future = widget.service.getBill(widget.billId);
  }

  void _reload() {
    setState(() {
      _future = widget.service.getBill(widget.billId);
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
    String two(int number) => number.toString().padLeft(2, '0');

    return '${two(date.day)}/${two(date.month)}/${date.year} '
        '${two(date.hour)}:${two(date.minute)} MYT';
  }

  String _status(dynamic value) {
    return {
      'issued': 'Awaiting payment',
      'paid': 'Paid',
      'void': 'Void',
      'pending': 'Payment pending',
      'failed': 'Payment failed',
      'cancelled': 'Cancelled',
      'expired': 'Expired',
      'refunded': 'Refunded',
    }[value] ?? value?.toString() ?? 'Unknown';
  }

  Widget _panel(List<Widget> children) {
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: 16),
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFFDDE7DF)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: children,
      ),
    );
  }

  Widget _heading(String text) {
    return Text(
      text,
      style: const TextStyle(
        fontSize: 17,
        fontWeight: FontWeight.bold,
      ),
    );
  }

  Widget _content(Map<String, dynamic> data) {
    final bill = Map<String, dynamic>.from(data['bill'] as Map);

    final items = (bill['items'] as List)
        .map((item) => Map<String, dynamic>.from(item as Map))
        .toList();

    final payments = (data['payments'] as List)
        .map((item) => Map<String, dynamic>.from(item as Map))
        .toList();

    final paid = bill['status'] == 'paid';
    final address = data['clinic_address']?.toString().trim() ?? '';
    final phone = data['clinic_phone']?.toString().trim() ?? '';
    final zeroTotal =
        num.tryParse(bill['total_amount'].toString()) == 0;

    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        _panel([
          Text(
            data['clinic_name'].toString(),
            style: const TextStyle(
              fontSize: 21,
              fontWeight: FontWeight.bold,
            ),
          ),
          if (address.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(address),
          ],
          if (phone.isNotEmpty) ...[
            const SizedBox(height: 6),
            Text('Phone: $phone'),
          ],
          const Divider(height: 28),
          Row(
            children: [
              Expanded(
                child: _heading(
                  'Bill #${bill['consultation_bill_id']}',
                ),
              ),
              const SizedBox(width: 12),
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 10,
                  vertical: 7,
                ),
                decoration: BoxDecoration(
                  color: paid
                      ? const Color(0xFFE8F3EB)
                      : const Color(0xFFFFF3DB),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  _status(bill['status']),
                  style: TextStyle(
                    color: paid ? _green : const Color(0xFF805B00),
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Text('Pet: ${data['pet_name']}'),
          const SizedBox(height: 6),
          Text('Appointment #${data['appointment_id']}'),
          const SizedBox(height: 6),
          Text('Consultation #${bill['consultation_id']}'),
          const SizedBox(height: 6),
          Text('Issued: ${_date(bill['issued_at'])}'),
        ]),
        _panel([
          _heading('Itemized charges'),
          const SizedBox(height: 16),
          ...items.map((item) {
            return Padding(
              padding: const EdgeInsets.only(bottom: 18),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          item['description'].toString(),
                          style: const TextStyle(
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        const SizedBox(height: 5),
                        Text(
                          '${item['quantity']} × '
                              '${_money(item['unit_price'])}',
                          style: const TextStyle(
                            color: Colors.black54,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 12),
                  Text(_money(item['subtotal'])),
                ],
              ),
            );
          }),
          const Divider(),
          const SizedBox(height: 10),
          Row(
            children: [
              const Expanded(
                child: Text(
                  'Total',
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
              Text(
                _money(bill['total_amount']),
                style: const TextStyle(
                  color: _green,
                  fontSize: 21,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ],
          ),
        ]),
        if (bill['status'] == 'issued')
          _panel([
            _heading('Payment'),
            const SizedBox(height: 10),
            const Text(
              'Pay this bill at the clinic. Staff will confirm '
                  'your payment after receiving the cash.',
              style: TextStyle(height: 1.5),
            ),
          ]),
        if (bill['status'] == 'void')
          _panel([
            const Text(
              'This bill has been voided. Contact the clinic '
                  'if you need clarification.',
              style: TextStyle(height: 1.5),
            ),
          ]),
        _panel([
          _heading('Payments & receipts'),
          const SizedBox(height: 12),
          if (payments.isEmpty)
            Text(
              paid && zeroTotal
                  ? 'No payment was required for this bill.'
                  : 'No payment has been recorded yet.',
            ),
          ...payments.map((payment) {
            final receipt =
                payment['receipt_number']?.toString() ?? '';

            return Padding(
              padding: const EdgeInsets.only(bottom: 16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    _money(payment['amount']),
                    style: const TextStyle(
                      fontSize: 17,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    payment['payment_method'] == 'cash'
                        ? 'Cash at clinic'
                        : 'Online payment',
                  ),
                  Text('Status: ${_status(payment['payment_status'])}'),
                  if (payment['payment_date'] != null)
                    Text('Paid: ${_date(payment['payment_date'])}'),
                  if (receipt.isNotEmpty) ...[
                    const SizedBox(height: 6),
                    SelectableText('Receipt: $receipt'),
                  ],
                ],
              ),
            );
          }),
        ]),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF5F7F5),
      appBar: AppBar(
        title: Text('Bill #${widget.billId}'),
        actions: [
          IconButton(
            tooltip: 'Refresh bill',
            onPressed: _reload,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: FutureBuilder<Map<String, dynamic>>(
        future: _future,
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
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
                      onPressed: _reload,
                      child: const Text('Try again'),
                    ),
                  ],
                ),
              ),
            );
          }

          return _content(snapshot.data!);
        },
      ),
    );
  }
}