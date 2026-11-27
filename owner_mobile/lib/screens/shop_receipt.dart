import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:pdf/pdf.dart';
import 'package:pdf/widgets.dart' as pw;
import 'package:printing/printing.dart';

import '../services/checkout_service.dart';

class ShopReceiptScreen extends StatefulWidget {
  final CheckoutService service;
  final int orderId;

  const ShopReceiptScreen({
    super.key,
    required this.service,
    required this.orderId,
  });

  @override
  State<ShopReceiptScreen> createState() =>
      _ShopReceiptScreenState();
}

class _ShopReceiptScreenState extends State<ShopReceiptScreen> {
  late Future<Uint8List> _future;

  @override
  void initState() {
    super.initState();
    _future = _loadReceipt();
  }

  void _retry() {
    setState(() => _future = _loadReceipt());
  }

  String _money(dynamic value) {
    final amount = num.tryParse('$value');

    if (amount == null || !amount.isFinite) {
      throw StateError('The receipt contains an invalid amount.');
    }

    return 'RM ${amount.toStringAsFixed(2)}';
  }

  String _date(dynamic value) {
    final parsed = DateTime.tryParse('${value ?? ''}');

    if (parsed == null) return 'Not recorded';

    final malaysia = parsed.toUtc().add(
      const Duration(hours: 8),
    );

    String two(int value) => value.toString().padLeft(2, '0');

    return '${two(malaysia.day)}/${two(malaysia.month)}/'
        '${malaysia.year} '
        '${two(malaysia.hour)}:${two(malaysia.minute)} MYT';
  }

  String _paymentMethod(dynamic value) {
    switch (value) {
      case 'cash':
        return 'Cash at clinic pickup';
      case 'card':
        return 'Card';
      case 'fpx':
        return 'FPX online banking';
      case 'online_banking':
        return 'Online payment';
      default:
        return 'Payment recorded';
    }
  }

  Future<Uint8List> _loadReceipt() async {
    // Fetch fresh, authenticated order data before creating a receipt.
    final order = await widget.service.getOrder(widget.orderId);

    if (order['payment_status'] != 'paid') {
      throw StateError(
        'A paid receipt is unavailable for this order. '
            'Check its payment or refund status.',
      );
    }

    if (order['payment_id'] is! int ||
        order['paid_amount'] == null) {
      throw StateError(
        'Payment details are unavailable. Refresh and try again.',
      );
    }

    final items = (order['items'] as List)
        .map((item) => Map<String, dynamic>.from(item as Map))
        .toList();

    final receiptNumber =
    '${order['receipt_number'] ?? ''}'.trim();

    // Use the real payment ID if a receipt number was not assigned.
    final reference = receiptNumber.isNotEmpty
        ? receiptNumber
        : 'Payment #${order['payment_id']}';

    final regularFont = await PdfGoogleFonts.notoSansRegular();
    final boldFont = await PdfGoogleFonts.notoSansBold();

    final document = pw.Document();

    final navy = PdfColor.fromHex('#172333');
    final blue = PdfColor.fromHex('#2549C7');
    final paleBlue = PdfColor.fromHex('#EEF2FF');

    pw.Widget amountRow(
        String title,
        dynamic amount, {
          bool total = false,
        }) {
      return pw.Padding(
        padding: const pw.EdgeInsets.symmetric(vertical: 5),
        child: pw.Row(
          mainAxisAlignment: pw.MainAxisAlignment.spaceBetween,
          children: [
            pw.Text(
              title,
              style: pw.TextStyle(
                fontWeight:
                total ? pw.FontWeight.bold : pw.FontWeight.normal,
              ),
            ),
            pw.Text(
              _money(amount),
              style: pw.TextStyle(
                fontWeight:
                total ? pw.FontWeight.bold : pw.FontWeight.normal,
              ),
            ),
          ],
        ),
      );
    }

    document.addPage(
      pw.MultiPage(
        pageFormat: PdfPageFormat.a4,
        margin: const pw.EdgeInsets.all(36),
        theme: pw.ThemeData.withFont(
          base: regularFont,
          bold: boldFont,
        ),
        footer: (context) => pw.Padding(
          padding: const pw.EdgeInsets.only(top: 12),
          child: pw.Row(
            mainAxisAlignment: pw.MainAxisAlignment.spaceBetween,
            children: [
              pw.Text(
                'Generated from the clinic payment record.',
                style: const pw.TextStyle(fontSize: 9),
              ),
              pw.Text(
                '${context.pageNumber} / ${context.pagesCount}',
                style: const pw.TextStyle(fontSize: 9),
              ),
            ],
          ),
        ),
        build: (context) => [
          pw.Text(
            '${order['clinic_name']}',
            style: pw.TextStyle(
              fontSize: 23,
              fontWeight: pw.FontWeight.bold,
              color: navy,
            ),
          ),
          pw.SizedBox(height: 8),
          pw.Text(
            'SHOP PAYMENT RECEIPT',
            style: pw.TextStyle(
              fontSize: 13,
              fontWeight: pw.FontWeight.bold,
              color: blue,
            ),
          ),
          pw.SizedBox(height: 20),

          pw.Container(
            width: double.infinity,
            padding: const pw.EdgeInsets.all(14),
            decoration: pw.BoxDecoration(
              color: paleBlue,
              borderRadius: pw.BorderRadius.circular(8),
            ),
            child: pw.Column(
              crossAxisAlignment: pw.CrossAxisAlignment.start,
              children: [
                pw.Text('Reference: $reference'),
                pw.SizedBox(height: 5),
                pw.Text('Order #${order['order_id']}'),
                pw.Text('Order date: ${_date(order['order_date'])}'),
                pw.Text('Payment date: ${_date(order['payment_date'])}'),
                pw.Text(
                  'Payment method: '
                      '${_paymentMethod(order['payment_method'])}',
                ),
                pw.Text('Payment status: Paid'),
              ],
            ),
          ),

          pw.SizedBox(height: 20),
          pw.Text(
            'Recipient',
            style: pw.TextStyle(fontWeight: pw.FontWeight.bold),
          ),
          pw.Text('${order['recipient_name']}'),
          pw.Text('${order['recipient_phone']}'),
          pw.SizedBox(height: 8),
          pw.Text(
            order['shipping_method'] == 'pickup'
                ? 'Fulfilment: Clinic pickup'
                : 'Fulfilment: Delivery',
          ),
          pw.Text('${order['shipping_address']}'),
          if (order['shipping_method'] == 'delivery') ...[
            pw.SizedBox(height: 5),
            pw.Text(
              'Destination state: '
                  '${order['delivery_state'] ?? 'Not recorded'}',
            ),
          ],
          pw.SizedBox(height: 24),

          pw.TableHelper.fromTextArray(
            headers: [
              'Product',
              'Quantity',
              'Unit price',
              'Amount',
            ],
            data: [
              for (final item in items)
                [
                  '${item['product_name']}',
                  '${item['quantity']}',
                  _money(item['unit_price']),
                  _money(item['subtotal']),
                ],
            ],
            headerStyle: pw.TextStyle(
              color: PdfColors.white,
              fontWeight: pw.FontWeight.bold,
            ),
            headerDecoration: pw.BoxDecoration(color: blue),
            cellStyle: const pw.TextStyle(fontSize: 10),
            cellPadding: const pw.EdgeInsets.all(8),
            columnWidths: {
              0: const pw.FlexColumnWidth(4),
              1: const pw.FlexColumnWidth(1),
              2: const pw.FlexColumnWidth(2),
              3: const pw.FlexColumnWidth(2),
            },
          ),

          pw.SizedBox(height: 18),
          amountRow('Subtotal', order['subtotal']),
          amountRow(
            'Delivery / pickup fee',
            order['shipping_fee'],
          ),
          pw.Divider(),
          amountRow('Order total', order['total_amount'], total: true),
          amountRow('Amount paid', order['paid_amount'], total: true),
          pw.SizedBox(height: 20),
          pw.Text(
            'Thank you for shopping with your clinic.',
            style: pw.TextStyle(color: navy),
          ),
        ],
      ),
    );

    return document.save();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Shop receipt')),
      body: FutureBuilder<Uint8List>(
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
                      '${snapshot.error}',
                      textAlign: TextAlign.center,
                    ),
                    const SizedBox(height: 12),
                    TextButton(
                      onPressed: _retry,
                      child: const Text('Try again'),
                    ),
                  ],
                ),
              ),
            );
          }

          final bytes = snapshot.data!;

          return PdfPreview(
            build: (_) async => bytes,
            pdfFileName: 'shop-receipt-${widget.orderId}.pdf',
            canChangeOrientation: false,
            canChangePageFormat: false,
            allowPrinting: true,
            allowSharing: false,
            canDebug: false,
            actions: [
              PdfPreviewAction(
                icon: const Icon(Icons.save_alt_rounded),
                onPressed: (context, build, pageFormat) async {
                  try {
                    await Printing.sharePdf(
                      bytes: bytes,
                      filename:
                      'shop-receipt-${widget.orderId}.pdf',
                    );
                  } catch (_) {
                    if (!context.mounted) return;

                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(
                        content: Text('Could not save or share the PDF.'),
                      ),
                    );
                  }
                },
              ),
            ],
          );
        },
      ),
    );
  }
}