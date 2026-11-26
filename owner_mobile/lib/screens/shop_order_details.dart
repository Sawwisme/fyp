import 'package:flutter/material.dart';

import '../services/checkout_service.dart';
import 'package:url_launcher/url_launcher.dart';
import 'shop_refunds.dart';
import 'shop_receipt.dart';

class ShopOrderDetailsScreen extends StatefulWidget {
  final CheckoutService service;
  final int orderId;

  const ShopOrderDetailsScreen({
    super.key,
    required this.service,
    required this.orderId,
  });

  @override
  State<ShopOrderDetailsScreen> createState() =>
      _ShopOrderDetailsScreenState();
}

class _ShopOrderDetailsScreenState
    extends State<ShopOrderDetailsScreen>
    with WidgetsBindingObserver {
  static const _green = Color(0xFF2549C7);

  Map<String, dynamic>? _order;
  String? _error;
  bool _loading = false;
  bool _cancelling = false;
  bool _openingPayment = false;
  bool _checkingPayment = false;
  bool _awaitingPaymentReturn = false;
  bool _refreshAfterOpening = false;

  String? _paymentMessage;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _load();
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

    _refreshPaymentResult();
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
    String two(int value) => value.toString().padLeft(2, '0');

    return '${two(date.day)}/${two(date.month)}/${date.year} '
        '${two(date.hour)}:${two(date.minute)} MYT';
  }

  String _label(dynamic value) {
    final text = value?.toString() ?? 'Unknown';
    return text
        .split('_')
        .map((word) => word.isEmpty
        ? word
        : '${word[0].toUpperCase()}${word.substring(1)}')
        .join(' ');
  }

  Future<void> _load() async {
    if (_loading) return;

    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final order = await widget.service.getOrder(widget.orderId);
      if (!mounted) return;
      setState(() {
        _order = order;

        final acceptedStatuses = {
          'paid',
          'processing',
          'ready_for_pickup',
          'shipped',
          'completed',
        };

        if (order['payment_status'] == 'paid' &&
            acceptedStatuses.contains(order['order_status'])) {
          _paymentMessage = 'Payment confirmed.';
        } else if (order['order_status'] != 'pending_payment' &&
            _paymentMessage != null) {
          _paymentMessage = 'The order status has been updated.';
        }
      });
    } catch (error) {
      if (mounted) {
        setState(() => _error = error.toString());
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _pay() async {
    if (_openingPayment || _checkingPayment || _loading || _cancelling || _order?['payment_method'] != 'online_banking' || _order?['order_status'] != 'pending_payment' || _order?['payment_status'] != 'pending') {
      return;
    }

    setState(() {
      _openingPayment = true;
      _paymentMessage = null;
    });

    try {
      final checkout = await widget.service.openStripeCheckout(
        widget.orderId,
      );

      if (!mounted) return;

      final uri = Uri.tryParse(
        checkout['checkout_url']?.toString() ?? '',
      );

      if (checkout['order_id'] != widget.orderId ||
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
        throw Exception('Cannot open the payment page on this device.');
      }

      if (mounted) {
        setState(() {
          _paymentMessage =
          'Complete payment in your browser, then return here. '
              'Your order updates after payment is verified.';
        });
      }
    } catch (error) {
      _awaitingPaymentReturn = false;

      if (mounted) {
        setState(() {
          _paymentMessage =
          '$error\n'
              'Refresh the order before trying again. '
              'Pay now reuses the same saved payment request.';
        });

        await _load();
      }
    } finally {
      if (mounted) {
        setState(() => _openingPayment = false);

        if (_refreshAfterOpening) {
          _refreshAfterOpening = false;
          _refreshPaymentResult();
        }
      }
    }
  }

  Future<void> _openReceipt() async {
    if (_loading ||
        _cancelling ||
        _openingPayment ||
        _checkingPayment) {
      return;
    }

    await Navigator.of(context).push<void>(
      MaterialPageRoute(
        builder: (_) => ShopReceiptScreen(
          service: widget.service,
          orderId: widget.orderId,
        ),
      ),
    );
  }

  Future<void> _refreshPaymentResult() async {
    if (!mounted || _checkingPayment) return;

    _awaitingPaymentReturn = false;

    setState(() {
      _checkingPayment = true;
      _paymentMessage = 'Checking payment confirmation…';
    });

    try {
      // The webhook worker may need a few seconds to confirm payment.
      for (var attempt = 0; attempt < 6; attempt++) {
        if (!mounted) return;

        if (WidgetsBinding.instance.lifecycleState !=
            AppLifecycleState.resumed) {
          _awaitingPaymentReturn = true;
          return;
        }

        await _load();

        if (!mounted) return;

        if (_error != null ||
            _order?['order_status'] != 'pending_payment' ||
            _order?['payment_status'] == 'paid') {
          break;
        }

        if (attempt < 5) {
          await Future<void>.delayed(const Duration(seconds: 2));
        }
      }

      if (!mounted) return;

      final paidAndAccepted =
          _order?['payment_status'] == 'paid' &&
              {
                'paid',
                'processing',
                'ready_for_pickup',
                'shipped',
                'completed',
              }.contains(_order?['order_status']);

      setState(() {
        if (_error != null) {
          _paymentMessage =
          'Could not check payment confirmation. '
              'Use Refresh order to try again.';
        } else if (paidAndAccepted) {
          _paymentMessage = 'Payment confirmed.';
        } else if (_order?['order_status'] != 'pending_payment') {
          _paymentMessage = 'The order status has been updated.';
        } else {
          _paymentMessage =
          'Payment is not confirmed yet. '
              'If you completed payment, refresh again shortly.';
        }
      });
    } finally {
      if (mounted) {
        setState(() => _checkingPayment = false);
      }
    }
  }

  Future<void> _cancel() async {
    if (_cancelling || _loading || _openingPayment || _checkingPayment) {
      return;
    }

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Cancel order?'),
        content: const Text(
          'This will cancel your unpaid order and release its reserved stock.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Keep order'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Cancel order'),
          ),
        ],
      ),
    );

    if (confirmed != true || !mounted) return;

    setState(() => _cancelling = true);

    String? failure;

    try {
      await widget.service.cancelOrder(widget.orderId);
    } catch (error) {
      failure = error.toString();
    }

    // Read the saved state even if the cancellation response was lost.
    await _load();

    if (!mounted) return;

    setState(() => _cancelling = false);

    if (failure != null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            'Cancellation could not be confirmed: $failure',
          ),
        ),
      );
    }
  }

  Widget _panel(List<Widget> children) {
    return Container(
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

  Widget _amount(String label, dynamic value, {bool total = false}) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 7),
      child: Row(
        children: [
          Expanded(child: Text(label)),
          Text(
            _money(value),
            style: TextStyle(
              color: total ? _green : null,
              fontSize: total ? 21 : 15,
              fontWeight: total ? FontWeight.bold : FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }

  Widget _body() {
    if (_order == null) {
      if (_loading) {
        return const Center(child: CircularProgressIndicator());
      }

      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(_error ?? 'Order unavailable.'),
              const SizedBox(height: 12),
              OutlinedButton(
                onPressed: _load,
                child: const Text('Try again'),
              ),
            ],
          ),
        ),
      );
    }

    final order = _order!;
    final pending = order['order_status'] == 'pending_payment';
    final cash = order['payment_method'] == 'cash';

    final canCancel = order['payment_status'] == 'pending' &&
        (pending || (cash && order['order_status'] == 'confirmed'));
    final busy = _loading || _cancelling || _openingPayment || _checkingPayment;

    return ListView(
      padding: const EdgeInsets.all(20),
      children: [
        if (_loading) const LinearProgressIndicator(),
        if (_error != null)
          Padding(
            padding: const EdgeInsets.only(bottom: 16),
            child: Text(
              'Could not refresh: $_error',
              style: const TextStyle(color: Colors.red),
            ),
          ),
        _panel([
          Text(
            order['clinic_name'].toString(),
            style: const TextStyle(
              fontSize: 21,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 8),
          Text('Order #${order['order_id']}'),
          const SizedBox(height: 14),
          Container(
            padding: const EdgeInsets.symmetric(
              horizontal: 12,
              vertical: 7,
            ),
            decoration: BoxDecoration(
              color: const Color(0xFFE8F3EB),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Text(
              _label(order['order_status']),
              style: const TextStyle(
                color: _green,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
          const SizedBox(height: 12),
          Text(
            'Payment method: '
                '${cash ? 'Cash at clinic pickup' : order['payment_method'] == 'card' ? 'Card' : order['payment_status'] == 'pending' ? 'Online payment (Card or FPX)' : 'FPX online banking'}',
          ),
          Text('Payment: ${_label(order['payment_status'])}'),
          Text('Placed: ${_date(order['order_date'])}'),
          if (cash &&
              order['payment_status'] == 'pending' &&
              {
                'confirmed',
                'processing',
                'ready_for_pickup',
              }.contains(order['order_status'])) ...[
            const SizedBox(height: 12),
            const Text(
              'Pay the clinic when collecting your order. '
                  'Staff will confirm payment after receiving your cash.',
              style: TextStyle(
                color: Colors.black54,
                height: 1.5,
              ),
            ),
          ],
          if (pending) ...[
            const SizedBox(height: 12),
            Text(
              'Payment deadline: '
                  '${_date(order['payment_expires_at'])}',
            ),
            const SizedBox(height: 8),
            const Text(
              'Complete payment before the deadline. '
                  'Return here afterward to check confirmation.',
              style: TextStyle(color: Colors.black54),
            ),
          ],
        ]),
        _panel([
          Text(
            order['shipping_method'] == 'pickup'
                ? 'Clinic pickup'
                : 'Delivery',
            style: const TextStyle(
              fontSize: 17,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 12),
          Text(order['recipient_name'].toString()),
          Text(order['recipient_phone'].toString()),
          const SizedBox(height: 10),
          Text(order['shipping_address'].toString()),
          if (order['shipping_method'] == 'delivery') ...[
            const SizedBox(height: 6),
            Text(
              'Destination state: '
                  '${order['delivery_state'] ?? 'Not recorded'}',
            ),
          ],
          if ((order['owner_note']?.toString() ?? '').isNotEmpty) ...[
            const Divider(height: 28),
            Text('Note: ${order['owner_note']}'),
          ],
        ]),
        _panel([
          const Text(
            'Order summary',
            style: TextStyle(
              fontSize: 17,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 14),
          ...(order['items'] as List).map((entry) {
            final item = Map<String, dynamic>.from(entry as Map);

            return Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: Text(
                      '${item['product_name']} × ${item['quantity']}',
                    ),
                  ),
                  const SizedBox(width: 12),
                  Text(_money(item['subtotal'])),
                ],
              ),
            );
          }),
          const Divider(),
          _amount('Subtotal', order['subtotal']),
          _amount('Delivery / pickup fee', order['shipping_fee']),
          const Divider(),
          _amount('Total', order['total_amount'], total: true),
        ]),
        if (order['payment_status'] == 'paid') ...[
          OutlinedButton.icon(
            onPressed: busy || _error != null ? null : _openReceipt,
            icon: const Icon(Icons.receipt_long_outlined),
            label: const Text('View / save receipt'),
          ),
          const SizedBox(height: 16),
        ],
        if (_paymentMessage != null)
          Padding(
            padding: const EdgeInsets.only(bottom: 16),
            child: Text(
              _paymentMessage!,
              style: const TextStyle(
                color: _green,
                height: 1.5,
              ),
            ),
          ),

        if (!cash && pending && order['payment_status'] == 'pending') ...[
          FilledButton.icon(
            onPressed: busy || _error != null ? null : _pay,
            icon: const Icon(Icons.account_balance_outlined),
            label: Text(
              _openingPayment
                  ? 'Opening payment…'
                  : _checkingPayment
                  ? 'Checking payment…'
                  : 'Pay now',
            ),
            style: FilledButton.styleFrom(
              backgroundColor: _green,
              padding: const EdgeInsets.symmetric(vertical: 15),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(10),
              ),
            ),
          ),
          const SizedBox(height: 12),
        ],

        if ({
          'paid',
          'refunded',
        }.contains(order['payment_status'])) ...[
          OutlinedButton.icon(
            onPressed: busy || _error != null
                ? null
                : () async {
              await Navigator.of(context).push<void>(
                MaterialPageRoute(
                  builder: (_) => ShopRefundsScreen(
                    service: widget.service,
                    orderId: widget.orderId,
                  ),
                ),
              );

              if (mounted) {
                await _load();
              }
            },
            icon: const Icon(Icons.assignment_return_outlined),
            label: const Text('Refunds'),
            style: OutlinedButton.styleFrom(
              foregroundColor: _green,
              padding: const EdgeInsets.symmetric(vertical: 14),
            ),
          ),
          const SizedBox(height: 12),
        ],

        if (canCancel)
          OutlinedButton(
            onPressed: busy || _error != null ? null : _cancel,
            style: OutlinedButton.styleFrom(
              foregroundColor: Colors.red.shade700,
              padding: const EdgeInsets.symmetric(vertical: 14),
            ),
            child: Text(
              _cancelling ? 'Cancelling…' : 'Cancel order',
            ),
          ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: !_cancelling && !_openingPayment,
      child: Scaffold(
        backgroundColor: const Color(0xFFEEF1F5),
        appBar: AppBar(
          title: Text('Order #${widget.orderId}'),
          actions: [
            IconButton(
              tooltip: 'Refresh order',
              onPressed: _loading || _cancelling || _openingPayment || _checkingPayment
                  ? null
                  : _load,
              icon: const Icon(Icons.refresh),
            ),
          ],
        ),
        body: _body(),
      ),
    );
  }
}