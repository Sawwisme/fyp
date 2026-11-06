import 'package:flutter/material.dart';

import '../services/checkout_service.dart';

class ShopRefundsScreen extends StatefulWidget {
  final CheckoutService service;
  final int orderId;

  const ShopRefundsScreen({
    super.key,
    required this.service,
    required this.orderId,
  });

  @override
  State<ShopRefundsScreen> createState() =>
      _ShopRefundsScreenState();
}

class _ShopRefundsScreenState extends State<ShopRefundsScreen> {
  static const _green = Color(0xFF2549C7);

  Map<String, dynamic>? _order;
  List<Map<String, dynamic>> _refunds = [];
  String? _error;
  String? _message;
  bool _loading = false;
  bool _sending = false;

  bool get _canRequest =>
      _order?['payment_status'] == 'paid' &&
          _refunds.every((item) => item['status'] == 'rejected');

  @override
  void initState() {
    super.initState();
    _load();
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
    switch (value) {
      case 'pending':
        return 'Awaiting clinic review';
      case 'approved':
        return 'Approved';
      case 'processing':
        return 'Refund processing';
      case 'requires_action':
        return 'Action required';
      case 'succeeded':
        return 'Refund successful';
      case 'rejected':
        return 'Request rejected';
      case 'failed':
        return 'Refund needs attention';
      default:
        return 'Status unavailable';
    }
  }

  String _explanation(dynamic value) {
    switch (value) {
      case 'pending':
        return 'The clinic will review your request.';
      case 'approved':
        return 'The clinic approved your request. '
            'The refund has not been completed yet.';
      case 'processing':
        return 'Your online refund is being processed.';
      case 'requires_action':
        return 'Additional action is needed. '
            'Check your payment emails or contact the clinic.';
      case 'succeeded':
        return 'The refund has been recorded as successful. '
            'Online refunds may take additional time to appear '
            'in your bank account.';
      case 'rejected':
        return 'Read the clinic’s explanation below.';
      case 'failed':
        return 'The refund could not be completed. '
            'Contact the clinic for assistance.';
      default:
        return 'Contact the clinic for details.';
    }
  }

  Future<void> _load() async {
    if (_loading) return;

    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final order = await widget.service.getOrder(widget.orderId);
      final refunds = await widget.service.getOrderRefunds(
        widget.orderId,
      );

      if (!mounted) return;

      setState(() {
        _order = order;
        _refunds = refunds;
      });
    } catch (error) {
      if (mounted) {
        setState(() => _error = error.toString());
      }
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  Future<void> _requestRefund() async {
    if (_loading || _sending || _error != null || !_canRequest) {
      return;
    }

    final controller = TextEditingController();
    final formKey = GlobalKey<FormState>();
    String? reason;

    try {
      final confirmed = await showDialog<bool>(
        context: context,
        builder: (dialogContext) => AlertDialog(
          title: const Text('Request a refund'),
          content: SingleChildScrollView(
            child: Form(
              key: formKey,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Full order amount: '
                        '${_money(_order?['total_amount'])}',
                  ),
                  const SizedBox(height: 12),
                  const Text(
                    'Submitting a request does not immediately '
                        'cancel your order or return your payment. '
                        'The clinic must review it first.',
                  ),
                  const SizedBox(height: 18),
                  TextFormField(
                    controller: controller,
                    minLines: 3,
                    maxLines: 5,
                    maxLength: 1000,
                    decoration: const InputDecoration(
                      labelText: 'Reason for refund',
                      hintText: 'Explain what happened',
                      alignLabelWithHint: true,
                      border: OutlineInputBorder(),
                    ),
                    validator: (value) {
                      if ((value ?? '').trim().length < 5) {
                        return 'Enter at least 5 characters.';
                      }
                      return null;
                    },
                  ),
                ],
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () =>
                  Navigator.pop(dialogContext, false),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () {
                if (formKey.currentState!.validate()) {
                  Navigator.pop(dialogContext, true);
                }
              },
              style: FilledButton.styleFrom(
                backgroundColor: _green,
              ),
              child: const Text('Submit request'),
            ),
          ],
        ),
      );

      if (confirmed == true) {
        reason = controller.text.trim();
      }
    } finally {
      controller.dispose();
    }

    if (reason == null || !mounted) return;

    setState(() {
      _sending = true;
      _message = null;
    });

    try {
      await widget.service.requestRefund(
        orderId: widget.orderId,
        reason: reason,
      );

      if (mounted) {
        setState(() {
          _message =
          'Your refund request is saved. '
              'Its current status appears below.';
        });
      }
    } catch (error) {
      if (mounted) {
        setState(() {
          _message =
          'Submission could not be confirmed: $error\n'
              'Check the saved requests below before trying again.';
        });
      }
    } finally {
      // Read the saved request even if the POST response was lost.
      if (mounted) {
        await _load();
      }
      if (mounted) {
        setState(() => _sending = false);
      }
    }
  }

  Widget _panel(List<Widget> children) {
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: 16),
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFFDDE7DF)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: children,
      ),
    );
  }

  Widget _refundCard(Map<String, dynamic> refund) {
    final status = refund['status'];
    final attention = {
      'rejected',
      'failed',
      'requires_action',
    }.contains(status);

    final color = attention ? Colors.orange.shade900 : _green;
    final notes = refund['review_notes']?.toString().trim() ?? '';

    return _panel([
      Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: Text(
              'Refund #${refund['refund_id']}',
              style: const TextStyle(
                fontSize: 17,
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
          const SizedBox(width: 12),
          Text(
            _money(refund['refund_amount']),
            style: const TextStyle(
              color: _green,
              fontSize: 17,
              fontWeight: FontWeight.bold,
            ),
          ),
        ],
      ),
      const SizedBox(height: 14),
      Container(
        padding: const EdgeInsets.symmetric(
          horizontal: 12,
          vertical: 8,
        ),
        decoration: BoxDecoration(
          color: attention
              ? const Color(0xFFFFF3E0)
              : const Color(0xFFE8F3EB),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Text(
          _status(status),
          style: TextStyle(
            color: color,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
      const SizedBox(height: 12),
      Text(
        _explanation(status),
        style: const TextStyle(height: 1.5),
      ),
      const Divider(height: 28),
      const Text(
        'Your reason',
        style: TextStyle(fontWeight: FontWeight.w600),
      ),
      const SizedBox(height: 6),
      Text(refund['reason']?.toString() ?? 'Not provided'),
      if (notes.isNotEmpty) ...[
        const SizedBox(height: 16),
        const Text(
          'Clinic response',
          style: TextStyle(fontWeight: FontWeight.w600),
        ),
        const SizedBox(height: 6),
        Text(notes),
      ],
      const SizedBox(height: 16),
      Text(
        'Requested: ${_date(refund['requested_at'])}',
        style: const TextStyle(color: Colors.black54),
      ),
      if (refund['processed_at'] != null)
        Text(
          'Processed: ${_date(refund['processed_at'])}',
          style: const TextStyle(color: Colors.black54),
        ),
    ]);
  }

  @override
  Widget build(BuildContext context) {
    final busy = _loading || _sending;

    return PopScope(
      canPop: !_sending,
      child: Scaffold(
        backgroundColor: const Color(0xFFEEF1F5),
        appBar: AppBar(
          title: const Text('Refunds'),
          actions: [
            IconButton(
              tooltip: 'Refresh refund status',
              onPressed: busy ? null : _load,
              icon: const Icon(Icons.refresh),
            ),
          ],
        ),
        body: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            if (busy) ...[
              const LinearProgressIndicator(),
              const SizedBox(height: 16),
            ],
            _panel([
              Text(
                'Order #${widget.orderId}',
                style: const TextStyle(
                  fontSize: 21,
                  fontWeight: FontWeight.bold,
                ),
              ),
              if (_order != null) ...[
                const SizedBox(height: 8),
                Text(_order!['clinic_name'].toString()),
                const SizedBox(height: 8),
                Text(
                  'Order total: ${_money(_order!['total_amount'])}',
                ),
              ],
            ]),
            if (_error != null)
              _panel([
                Text(
                  'Could not refresh: $_error',
                  style: const TextStyle(color: Colors.red),
                ),
                const SizedBox(height: 8),
                TextButton(
                  onPressed: busy ? null : _load,
                  child: const Text('Try again'),
                ),
              ]),
            if (_message != null)
              Padding(
                padding: const EdgeInsets.only(bottom: 16),
                child: Text(
                  _message!,
                  style: const TextStyle(height: 1.5),
                ),
              ),
            if (_order != null &&
                _error == null &&
                _refunds.isEmpty)
              _panel([
                const Text(
                  'No refund requests yet',
                  style: TextStyle(
                    fontSize: 17,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  _canRequest
                      ? 'You can request a full-order refund. '
                      'The clinic will review your reason.'
                      : 'Refund requests are available after '
                      'payment has been confirmed.',
                ),
              ]),
            ..._refunds.map(_refundCard),
            if (_canRequest && _error == null)
              FilledButton.icon(
                onPressed: busy ? null : _requestRefund,
                icon: const Icon(Icons.assignment_return_outlined),
                label: Text(
                  _sending ? 'Submitting…' : 'Request refund',
                ),
                style: FilledButton.styleFrom(
                  backgroundColor: _green,
                  padding: const EdgeInsets.symmetric(vertical: 15),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(10),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}