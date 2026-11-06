import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

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

class _BillDetailsScreenState extends State<BillDetailsScreen>
    with WidgetsBindingObserver {
  static const _green = Color(0xFF176B32);

  late Future<Map<String, dynamic>> _future;
  bool _openingPayment = false;
  bool _checkingPayment = false;
  bool _cancellingPayment = false;
  bool _awaitingPaymentReturn = false;
  bool _refreshAfterOpening = false;
  String? _paymentMessage;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _future = widget.service.getBill(widget.billId);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state != AppLifecycleState.resumed ||
        !_awaitingPaymentReturn) {
      return;
    }

    if (_openingPayment) {
      _refreshAfterOpening = true;
      return;
    }

    _checkPaymentResult();
  }

  Future<void> _pay(Map<String, dynamic> data) async {
    if (_openingPayment ||
        _checkingPayment ||
        _cancellingPayment ||
        (data['bill'] as Map)['status'] != 'issued') {
      return;
    }

    setState(() {
      _openingPayment = true;
      _paymentMessage = null;
    });

    try {
      final checkout = await widget.service.openCheckout(
        widget.billId,
      );

      if (!mounted) return;

      final uri = Uri.tryParse(
        checkout['checkout_url']?.toString() ?? '',
      );

      if (checkout['consultation_bill_id'] != widget.billId ||
          uri == null ||
          uri.scheme != 'https' ||
          uri.host != 'checkout.stripe.com' ||
          uri.userInfo.isNotEmpty) {
        throw Exception('The server returned an invalid payment link.');
      }

      _awaitingPaymentReturn = true;

      final opened = await launchUrl(
        uri,
        mode: LaunchMode.externalApplication,
      );

      if (!opened) {
        throw Exception('Cannot open the payment page.');
      }

      if (mounted) {
        setState(() {
          _paymentMessage =
          'Complete payment in your browser, then return here. '
              'Confirmation appears after payment is verified.';
        });
      }
    } catch (error) {
      _awaitingPaymentReturn = false;

      if (mounted) {
        setState(() {
          _paymentMessage =
          '$error\nRefresh this bill before trying again. '
              'An existing pending payment will be reused.';
          _future = widget.service.getBill(widget.billId);
        });
      }
    } finally {
      if (mounted) {
        setState(() => _openingPayment = false);

        if (_refreshAfterOpening) {
          _refreshAfterOpening = false;
          _checkPaymentResult();
        }
      }
    }
  }

  Future<void> _checkPaymentResult() async {
    if (!mounted || _checkingPayment || _cancellingPayment) return;

    _awaitingPaymentReturn = false;

    setState(() {
      _checkingPayment = true;
      _paymentMessage = 'Checking payment confirmation…';
    });

    try {
      for (var attempt = 0; attempt < 7; attempt++) {
        if (!mounted) return;

        if (WidgetsBinding.instance.lifecycleState !=
            AppLifecycleState.resumed) {
          _awaitingPaymentReturn = true;
          return;
        }

        final data = await widget.service.getBill(widget.billId);
        if (!mounted) return;

        final status = (data['bill'] as Map)['status'];

        setState(() {
          _future = Future.value(data);
        });

        if (status == 'paid') {
          setState(() {
            _paymentMessage = 'Payment confirmed.';
          });
          return;
        }

        if (status != 'issued') {
          setState(() {
            _paymentMessage = 'The bill status has been updated.';
          });
          return;
        }

        if (attempt < 6) {
          await Future<void>.delayed(
            const Duration(seconds: 3),
          );
        }
      }

      if (mounted) {
        setState(() {
          _paymentMessage =
          'Payment is not confirmed yet. If you completed '
              'payment, refresh again shortly. Do not pay again '
              'while confirmation is pending.';
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          _paymentMessage =
          'Could not confirm payment. Refresh the bill '
              'to check its saved status before trying again.';
        });
      }
    } finally {
      if (mounted) {
        setState(() => _checkingPayment = false);
      }
    }
  }

  Future<void> _payAtClinic() async {
    if (_openingPayment ||
        _checkingPayment ||
        _cancellingPayment) {
      return;
    }

    setState(() => _cancellingPayment = true);

    try {
      final confirmed = await showDialog<bool>(
        context: context,
        barrierDismissible: false,
        builder: (dialogContext) => AlertDialog(
          title: const Text('Pay at clinic?'),
          content: const Text(
            'We will close your unpaid online payment page first. '
                'Your bill remains unpaid until clinic staff receive '
                'and confirm your cash payment.\n\n'
                'If online payment has already completed or is processing, '
                'switching to cash will be blocked.',
          ),
          actions: [
            TextButton(
              onPressed: () {
                Navigator.of(dialogContext).pop(false);
              },
              child: const Text('Keep online payment'),
            ),
            FilledButton(
              onPressed: () {
                Navigator.of(dialogContext).pop(true);
              },
              child: const Text('Pay at clinic'),
            ),
          ],
        ),
      );

      if (confirmed != true || !mounted) return;

      setState(() {
        _paymentMessage = 'Closing the online payment attempt…';
      });

      await widget.service.cancelOnlineAttempt(widget.billId);

      _awaitingPaymentReturn = false;
      _refreshAfterOpening = false;

      final data = await widget.service.getBill(widget.billId);
      if (!mounted) return;

      final status = (data['bill'] as Map)['status'];
      final payments = (data['payments'] as List).cast<Map>();

      final hasUnresolvedPayment = payments.any(
            (payment) => ![
          'failed',
          'cancelled',
          'expired',
        ].contains(payment['payment_status']),
      );

      setState(() {
        _future = Future.value(data);

        if (status == 'paid') {
          _paymentMessage =
          'Payment is already confirmed. No cash payment is needed.';
        } else if (status == 'issued' && !hasUnresolvedPayment) {
          _paymentMessage =
          'The online payment attempt is closed. '
              'You can pay cash at the clinic. '
              'Staff will confirm payment after receiving it.';
        } else {
          _paymentMessage =
          'The bill status has changed. Contact the clinic '
              'before making another payment.';
        }
      });
    } catch (error) {
      if (!mounted) return;

      setState(() {
        _paymentMessage =
        '$error\nRefresh the bill before paying at the clinic.';
        _future = widget.service.getBill(widget.billId);
      });
    } finally {
      if (mounted) {
        setState(() => _cancellingPayment = false);
      }
    }
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

  Widget _billAmountLine(
      String title,
      dynamic value, {
        bool emphasis = false,
      }) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 7),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: Text(
              title,
              style: TextStyle(
                fontWeight:
                emphasis ? FontWeight.bold : FontWeight.normal,
              ),
            ),
          ),
          const SizedBox(width: 16),
          Text(
            _money(value),
            style: TextStyle(
              color: emphasis ? _green : null,
              fontWeight: FontWeight.bold,
              fontSize: emphasis ? 20 : 15,
            ),
          ),
        ],
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
    final amount = num.tryParse(
      bill['balance_amount'].toString(),
    );

    final depositApplied = num.tryParse(
      bill['deposit_applied_amount']?.toString() ?? '',
    ) ?? 0;

    final excessRefund = num.tryParse(
      bill['deposit_excess_refund_amount']?.toString() ?? '',
    ) ?? 0;

    final onlineEligible =
        amount != null && amount >= 1 && amount <= 30000;

    final pendingOnline = payments.any(
          (payment) =>
      payment['payment_status'] == 'pending' &&
          payment['payment_method'] == 'online_banking',
    );

    final blockingPayment = payments.any(
          (payment) =>
      payment['payment_status'] == 'paid' ||
          payment['payment_status'] == 'refunded' ||
          (!{'failed', 'cancelled', 'expired'}.contains(
            payment['payment_status'],
          ) &&
              payment['payment_method'] != 'online_banking'),
    );

    final busy =
        _openingPayment || _checkingPayment || _cancellingPayment;

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
                  'Total charges',
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

        _panel([
          _heading('Deposit & balance'),
          const SizedBox(height: 12),
          _billAmountLine(
            'Booking deposit received',
            bill['deposit_paid_amount'],
          ),
          _billAmountLine(
            'Deposit applied',
            bill['deposit_applied_amount'],
          ),
          _billAmountLine(
            'Balance after deposit',
            bill['balance_amount'],
          ),
          const Divider(),
          _billAmountLine(
            'Amount still due',
            bill['amount_due'],
            emphasis: true,
          ),
          if (excessRefund > 0) ...[
            const SizedBox(height: 10),
            _billAmountLine(
              'Excess deposit refund amount',
              bill['deposit_excess_refund_amount'],
            ),
          ],
        ]),

        if (_paymentMessage != null)
          _panel([
            Text(
              paid ? 'Payment confirmed.' : _paymentMessage!,
              style: const TextStyle(
                color: _green,
                height: 1.5,
              ),
            ),
          ]),
        if (bill['status'] == 'issued')
          _panel([
            _heading('Payment'),
            const SizedBox(height: 10),
            Text(
              pendingOnline
                  ? 'An online payment attempt is pending. '
                  'Resume it or refresh this bill to check '
                  'whether payment was confirmed.'
                  : 'Pay online through FPX, or pay cash at the clinic. '
                  'Staff will confirm cash after receiving it.',
              style: const TextStyle(height: 1.5),
            ),
            if (onlineEligible && !blockingPayment) ...[
              const SizedBox(height: 16),
              SizedBox(
                width: double.infinity,
                child: FilledButton.icon(
                  onPressed: busy ? null : () => _pay(data),
                  icon: const Icon(Icons.account_balance_outlined),
                  label: Text(
                    _openingPayment
                        ? 'Opening payment…'
                        : _checkingPayment
                        ? 'Checking payment…'
                        : pendingOnline
                        ? 'Resume online payment'
                        : 'Pay online',
                  ),
                  style: FilledButton.styleFrom(
                    backgroundColor: _green,
                    padding: const EdgeInsets.symmetric(vertical: 15),
                  ),
                ),
              ),
            ],
            if (pendingOnline && !blockingPayment) ...[
              const SizedBox(height: 10),
              SizedBox(
                width: double.infinity,
                child: OutlinedButton.icon(
                  onPressed: busy ? null : _payAtClinic,
                  icon: const Icon(Icons.payments_outlined),
                  label: Text(
                    _cancellingPayment
                        ? 'Closing online attempt…'
                        : 'Pay at clinic instead',
                  ),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: _green,
                    padding: const EdgeInsets.symmetric(vertical: 15),
                  ),
                ),
              ),
            ],
            if (!onlineEligible) ...[
              const SizedBox(height: 12),
              const Text(
                'Please contact the clinic to pay this amount.',
                style: TextStyle(color: Colors.black54),
              ),
            ],
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
              paid && depositApplied > 0
                  ? 'This bill was settled using its booking deposit.'
                  : paid && zeroTotal
                  ? 'No payment was required for this bill.'
                  : 'No balance payment has been recorded yet.',
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
    final busy =
        _openingPayment || _checkingPayment || _cancellingPayment;

    return PopScope(
      canPop: !_openingPayment && !_cancellingPayment,
      child: Scaffold(
        backgroundColor: const Color(0xFFF5F7F5),
        appBar: AppBar(
          title: Text('Bill #${widget.billId}'),
          actions: [
            IconButton(
              tooltip: 'Refresh bill',
              onPressed: busy ? null : _reload,
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
                        onPressed: busy ? null : _reload,
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
      ),
    );
  }
}