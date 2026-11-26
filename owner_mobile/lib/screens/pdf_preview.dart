import 'dart:typed_data';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:printing/printing.dart';

class ReportPdfPreviewPage extends StatefulWidget {
  final Uint8List bytes;
  final String filename;
  final String title;

  const ReportPdfPreviewPage({
    super.key,
    required this.bytes,
    required this.filename,
    required this.title,
  });

  @override
  State<ReportPdfPreviewPage> createState() =>
      _ReportPdfPreviewPageState();
}

class _ReportPdfPreviewPageState
    extends State<ReportPdfPreviewPage> {
  bool _saving = false;

  Future<void> _savePdf() async {
    if (_saving) return;

    setState(() => _saving = true);

    try {
      final savedFile = await FilePicker.saveFile(
        dialogTitle: 'Save PDF report',
        fileName: widget.filename,
        bytes: widget.bytes,
        mimeType: 'application/pdf',
      );

      // Cancellation is not a successful save.
      if (!mounted || savedFile == null) return;

      await showDialog<void>(
        context: context,
        builder: (dialogContext) => AlertDialog(
          icon: const Icon(
            Icons.check_circle_outline,
            color: Color(0xFF237A4B),
            size: 42,
          ),
          title: const Text('PDF saved'),
          content: Text(
            '${widget.filename}\n\n'
                'Saved successfully to your selected location.',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(dialogContext).pop(),
              child: const Text('OK'),
            ),
          ],
        ),
      );
    } catch (error, stackTrace) {
      debugPrint('PDF save failed: $error');
      debugPrintStack(stackTrace: stackTrace);
      if (!mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Could not save the PDF. Please try again.',
          ),
        ),
      );
    } finally {
      if (mounted) {
        setState(() => _saving = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.title),
        actions: [
          IconButton(
            tooltip: 'Save PDF',
            onPressed: _saving ? null : _savePdf,
            icon: _saving
                ? const SizedBox(
              width: 20,
              height: 20,
              child: CircularProgressIndicator(
                strokeWidth: 2,
              ),
            )
                : const Icon(Icons.download_outlined),
          ),
        ],
      ),
      body: PdfPreview(
        build: (_) async => widget.bytes,
        pdfFileName: widget.filename,
        canDebug: false,
        canChangePageFormat: false,
        canChangeOrientation: false,
        allowPrinting: true,
        allowSharing: true,
      ),
    );
  }
}