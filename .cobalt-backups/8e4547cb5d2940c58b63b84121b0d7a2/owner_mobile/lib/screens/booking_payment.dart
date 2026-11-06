import 'dart:async';

import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../services/appointment_service.dart';

class BookingPaymentScreen extends StatefulWidget {
  final AppointmentService service;
  final int appointmentId;

  const BookingPaymentScreen({
    super.key,
    required this.service,
    required this.appointmentId,
  });

  @override
  State<BookingPaymentScreen> createState() =>
      _BookingPaymentScreenState();
}

class _BookingPaymentScreenState
    extends State<BookingPaymentScreen>
    with WidgetsBindingObserver {
  static const _green = Color(0xFF176B32);

  Map<String, dynamic>? _data;
  String? _error;
  Map<String, dynamic>? _refund;
  String? _refundError;

  bool _busy = false;
  bool _awaitingReturn = false;
  bool _refreshOnIdle = false;

  Timer? _timer;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _refresh();

    _timer = Timer.periodic(
      const Duration(seconds: 15),
          (_) {
        final waitingForPayment =
            _data?['checkout_status'] == 'processing';

        final waitingForRefund = [
          'approved',
          'processing',
          'requires_action',
        ].contains(_refund?['status']);

        if (!_busy &&
            (waitingForPayment || waitingForRefund) &&
            WidgetsBinding.instance.lifecycleState ==
                AppLifecycleState.resumed) {
          _refresh();
        }
      },
    );
  }

  @override
  void dispose() {
    _timer?.cancel();
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state != AppLifecycleState.resumed ||
        !_awaitingReturn) {
      return;
    }

    _awaitingReturn = false;

    if (_busy) {
      _refreshOnIdle = true;
    } else {
      _refresh();
    }
  }

  Future<void> _refresh({bool pay = false}) async {
    if (!mounted || _busy) return;

    setState(() {
      _busy = true;
      _error = null;
    });

    try {
      final data = await widget.service.openBookingCheckout(
        widget.appointmentId,
      );

      if (!mounted) return;

      setState(() => _data = data);

      if ([
        'cancelled',
        'completed',
      ].contains(data['appointment_status']) ||
          [
            'refunded',
            'partially_refunded',
          ].contains(data['payment_status'])) {
        try {
          final refund = await widget.service.getBookingRefund(
            widget.appointmentId,
          );

          if (!mounted) return;

          setState(() {
            _refund = refund;
            _refundError = null;
          });
        } catch (error) {
          if (!mounted) return;

          setState(() {
            _refund = null;
            _refundError =
            'Cannot load refund details. Refresh to check again.';
          });
        }
      } else {
        setState(() {
          _refund = null;
          _refundError = null;
        });
      }

      if (!pay || data['checkout_url'] == null) return;

      final uri = Uri.tryParse(
        data['checkout_url'].toString(),
      );

      if (uri == null ||
          uri.scheme != 'https' ||
          uri.host != 'checkout.stripe.com' ||
          uri.userInfo.isNotEmpty ||
          (uri.hasPort && uri.port != 443)) {
        throw Exception('Invalid payment link.');
      }

      _awaitingReturn = true;

      final opened = await launchUrl(
        uri,
        mode: LaunchMode.externalApplication,
      );

      if (!opened) {
        throw Exception('Cannot open the payment page.');
      }
    } catch (error) {
      _awaitingReturn = false;

      if (mounted) {
        setState(() {
          _error =
          '$error\nRefresh to check the existing booking. '
              'Do not create another booking while payment '
              'confirmation is pending.';
        });
      }
    } finally {
      if (mounted) {
        setState(() => _busy = false);

        if (_refreshOnIdle) {
          _refreshOnIdle = false;
          _refresh();
        }
      }
    }
  }

  String _deadline(dynamic value) {
    final parsed = DateTime.tryParse(value?.toString() ?? '');
    if (parsed == null) return 'Not available';

    final date = parsed.toUtc().add(
      const Duration(hours: 8),
    );

    String two(int number) => number.toString().padLeft(2, '0');

    return '${two(date.day)}/${two(date.month)}/${date.year} '
        '${two(date.hour)}:${two(date.minute)} MYT';
  }

  Widget _refundPanel() {
    final refund = _refund;

    if (refund == null && _refundError == null) {
      return const SizedBox.shrink();
    }

    const labels = {
      'approved': 'Refund processing',
      'processing': 'Refund processing',
      'requires_action': 'Clinic assistance needed',
      'succeeded': 'Refund confirmed',
      'failed': 'Refund needs review',
    };

    const messages = {
      'approved':
      'Your refund has been approved '
          'and is waiting to be processed.',
      'processing':
      'Your refund is being processed. '
          'Refresh later to check its progress.',
      'requires_action':
      'The refund needs an additional step. '
          'Contact the clinic for assistance.',
      'succeeded':
      'Stripe has confirmed that your deposit refund succeeded.',
      'failed':
      'The refund could not be completed. '
          'Contact the clinic to review it.',
    };

    final status = refund?['status']?.toString();

    final amount = num.tryParse(
      refund?['refund_amount']?.toString() ?? '',
    );

    return Padding(
      padding: const EdgeInsets.only(top: 16),
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: const Color(0xFFDCE6DF),
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              refund?['refund_purpose'] == 'booking_excess'
                  ? 'Excess deposit: ${labels[status] ?? 'Refund status'}'
                  : labels[status] ?? 'Refund status',
              style: const TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.bold,
              ),
            ),
            if (refund != null) ...[
              const SizedBox(height: 12),
              Text(
                amount == null
                    ? '—'
                    : 'RM ${amount.toStringAsFixed(2)}',
                style: const TextStyle(
                  color: _green,
                  fontSize: 24,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 8),
              Text('Refund #${refund['refund_id']}'),
              const SizedBox(height: 10),
              Text(
                messages[status] ??
                    'Contact the clinic to check this refund.',
                style: const TextStyle(height: 1.5),
              ),
              const SizedBox(height: 12),
              Text(
                'Requested: ${_deadline(refund['requested_at'])}',
                style: const TextStyle(fontSize: 12),
              ),
              if (refund['processed_at'] != null) ...[
                const SizedBox(height: 6),
                Text(
                  'Updated: ${_deadline(refund['processed_at'])}',
                  style: const TextStyle(fontSize: 12),
                ),
              ],
            ],
            if (_refundError != null) ...[
              const SizedBox(height: 10),
              Text(
                _refundError!,
                style: TextStyle(
                  color: Theme.of(context).colorScheme.error,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _body() {
    final data = _data;

    if (data == null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: _busy
              ? const CircularProgressIndicator()
              : Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                _error ?? 'Cannot load booking payment.',
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 16),
              OutlinedButton(
                onPressed: () => _refresh(),
                child: const Text('Retry'),
              ),
            ],
          ),
        ),
      );
    }

    final appointmentStatus = data['appointment_status'];
    final checkoutStatus = data['checkout_status'];
    final refundStatus = _refund?['status'];

    final originalDeposit = num.tryParse(
      data['deposit_amount']?.toString() ?? '',
    ) ?? 0;

    final refundAmount = num.tryParse(
      _refund?['refund_amount']?.toString() ?? '',
    ) ?? 0;

    final refundSucceeded = refundStatus == 'succeeded';

    final refunded = data['payment_status'] == 'refunded' ||
        (refundSucceeded &&
            originalDeposit > 0 &&
            refundAmount >= originalDeposit);

    final paymentStatus = refunded
        ? 'refunded'
        : refundSucceeded
        ? 'partially_refunded'
        : data['payment_status'];

    final refundProcessing = [
      'approved',
      'processing',
    ].contains(refundStatus);

    final refundNeedsAttention = [
      'failed',
      'requires_action',
    ].contains(refundStatus);

    final confirmed = [
      'paid',
      'partially_refunded',
    ].contains(paymentStatus) &&
        [
          'confirmed',
          'in_progress',
          'completed',
        ].contains(appointmentStatus);

    final needsReview = !refunded &&
        !refundProcessing &&
        (refundNeedsAttention ||
            checkoutStatus == 'review_required' ||
            (paymentStatus == 'paid' && !confirmed));

    final closed = [
      'cancelled',
      'rejected',
    ].contains(appointmentStatus);

    final canPay = !confirmed &&
        !needsReview &&
        !closed &&
        appointmentStatus == 'pending_payment' &&
        paymentStatus == 'pending' &&
        data['checkout_url'] != null;

    final amount = num.tryParse(
      data['deposit_amount']?.toString() ?? '',
    );

    final String description;

    if (refunded) {
      description =
      'Your appointment deposit refund has been confirmed.';
    } else if (refundProcessing) {
      description =
      'Your deposit refund is being processed. '
          'You do not need to submit another refund request.';
    } else if (refundNeedsAttention) {
      description =
      'Your deposit refund needs attention. '
          'Contact the clinic for assistance.';
    } else if (needsReview) {
      description =
      'This booking needs a clinic review. Contact the clinic '
          'before making another payment.';
    } else if (confirmed) {
      description =
      'Your deposit has been verified and your appointment '
          'is confirmed.';
    } else if (closed) {
      description =
      'This booking is no longer active. '
          'Its payment status is shown below.';
    } else if (checkoutStatus == 'processing') {
      description =
      'Your bank payment is being checked. '
          'Do not pay again while confirmation is pending.';
    } else {
      description =
      'Complete your deposit payment before the deadline. '
          'Your appointment is confirmed after payment is verified.';
    }

    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        Container(
          padding: const EdgeInsets.all(22),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(18),
            border: Border.all(
              color: const Color(0xFFDCE6DF),
            ),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(
                confirmed
                    ? Icons.check_circle_outline
                    : needsReview
                    ? Icons.info_outline
                    : Icons.account_balance_outlined,
                color: _green,
                size: 36,
              ),
              const SizedBox(height: 16),
              Text(
                refunded
                    ? 'Deposit refunded'
                    : refundProcessing
                    ? 'Refund processing'
                    : confirmed
                    ? 'Appointment confirmed'
                    : 'Appointment deposit',
                style: const TextStyle(
                  fontSize: 23,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 6),
              Text('Booking #${widget.appointmentId}'),
              const SizedBox(height: 20),
              Text(
                amount == null
                    ? '—'
                    : 'RM ${amount.toStringAsFixed(2)}',
                style: const TextStyle(
                  color: _green,
                  fontSize: 30,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 16),
              Text(
                description,
                style: const TextStyle(height: 1.5),
              ),
              const Divider(height: 32),
              Text(
                'Booking: '
                    '${appointmentStatus.toString().replaceAll('_', ' ')}',
              ),
              const SizedBox(height: 8),
              Text(
                'Payment: '
                    '${paymentStatus.toString().replaceAll('_', ' ')}',
              ),
              if (appointmentStatus == 'pending_payment') ...[
                const SizedBox(height: 8),
                Text(
                  'Pay before: ${_deadline(data['payment_expires_at'])}',
                ),
              ],
            ],
          ),
        ),
        _refundPanel(),
        if (_error != null) ...[
          const SizedBox(height: 16),
          Text(
            _error!,
            style: TextStyle(
              color: Theme.of(context).colorScheme.error,
            ),
          ),
        ],
        if (canPay) ...[
          const SizedBox(height: 20),
          FilledButton.icon(
            onPressed: _busy
                ? null
                : () => _refresh(pay: true),
            icon: const Icon(Icons.account_balance_outlined),
            label: Text(
              _busy ? 'Please wait…' : 'Pay deposit online',
            ),
            style: FilledButton.styleFrom(
              backgroundColor: _green,
              padding: const EdgeInsets.symmetric(vertical: 15),
            ),
          ),
        ],
        const SizedBox(height: 12),
        OutlinedButton.icon(
          onPressed: _busy ? null : () => _refresh(),
          icon: const Icon(Icons.refresh),
          label: Text(
            _busy ? 'Checking…' : 'Refresh status',
          ),
        ),
        const SizedBox(height: 12),
        TextButton(
          onPressed: _busy
              ? null
              : () => Navigator.of(context).pop(true),
          child: const Text('Back to appointments'),
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: !_busy,
      child: Scaffold(
        backgroundColor: const Color(0xFFF5F7F5),
        appBar: AppBar(
          title: const Text('Booking payment'),
        ),
        body: _body(),
      ),
    );
  }
}