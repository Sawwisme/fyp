import 'dart:typed_data';

import 'package:pdf/pdf.dart';
import 'package:pdf/widgets.dart' as pw;
import 'package:printing/printing.dart';

class AssessmentPdfService {
  static Future<Uint8List> build({
    required Map<String, dynamic> job,
    required Map<String, dynamic> pet,
    required Uint8List originalImage,
    required Uint8List combinedImage,
  }) async {
    if (job['status'] != 'completed' || job['result'] is! Map) {
      throw StateError('Only completed assessments can be exported.');
    }

    final result = Map<String, dynamic>.from(job['result'] as Map);
    final decision = result['decision'] is Map
        ? Map<String, dynamic>.from(result['decision'] as Map)
        : <String, dynamic>{};
    final severity = result['severity'] is Map
        ? Map<String, dynamic>.from(result['severity'] as Map)
        : <String, dynamic>{};

    final regular = await PdfGoogleFonts.notoSansRegular();
    final bold = await PdfGoogleFonts.notoSansBold();
    final chinese = await PdfGoogleFonts.notoSansSCRegular();

    final document = pw.Document(
      theme: pw.ThemeData.withFont(
        base: regular,
        bold: bold,
        fontFallback: [chinese],
      ),
    );

    final blue = PdfColor.fromHex('#2549C7');
    final paleBlue = PdfColor.fromHex('#EDF2FF');

    String recorded(Object? value) {
      final text = value?.toString().trim() ?? '';
      return text.isEmpty ? 'Not available' : text;
    }

    String assessmentDate() {
      final value = DateTime.tryParse(
        job['finished_at']?.toString() ??
            job['created_at']?.toString() ??
            '',
      );
      if (value == null) return 'Not available';

      final date = value.toUtc().add(const Duration(hours: 8));
      String two(int n) => n.toString().padLeft(2, '0');

      return '${two(date.day)}/${two(date.month)}/${date.year} '
          '${two(date.hour)}:${two(date.minute)} MYT';
    }

    pw.Widget heading(String title) => pw.Padding(
      padding: const pw.EdgeInsets.only(top: 18, bottom: 8),
      child: pw.Text(
        title,
        style: pw.TextStyle(
          color: blue,
          fontSize: 15,
          fontWeight: pw.FontWeight.bold,
        ),
      ),
    );

    final rows = <List<String>>[];

    for (final item in result['predictions'] as List? ?? []) {
      if (item is! Map) continue;

      final assessed = item['assessed'] != false &&
          item['supported'] != false &&
          item['positive'] is bool;
      final confidence = item['confidence'];

      final score = assessed &&
          confidence is num &&
          confidence.isFinite &&
          confidence >= 0 &&
          confidence <= 1
          ? '${(confidence * 100).toStringAsFixed(1)}%'
          : 'Not available';

      rows.add([
        recorded(item['condition']),
        assessed
            ? (item['positive'] == true
            ? 'Above model threshold'
            : 'Below model threshold')
            : 'Not assessed',
        score,
      ]);
    }

    document.addPage(
      pw.MultiPage(
        pageFormat: PdfPageFormat.a4,
        margin: const pw.EdgeInsets.all(36),
        footer: (context) => pw.Padding(
          padding: const pw.EdgeInsets.only(top: 12),
          child: pw.Row(
            mainAxisAlignment: pw.MainAxisAlignment.spaceBetween,
            children: [
              pw.Text(
                'VetDental | AI screening reference',
                style: const pw.TextStyle(fontSize: 8),
              ),
              pw.Text(
                '${context.pageNumber} / ${context.pagesCount}',
                style: const pw.TextStyle(fontSize: 8),
              ),
            ],
          ),
        ),
        build: (_) => [
          pw.Container(
            width: double.infinity,
            padding: const pw.EdgeInsets.all(22),
            decoration: pw.BoxDecoration(
              color: blue,
              borderRadius: pw.BorderRadius.circular(12),
            ),
            child: pw.Column(
              crossAxisAlignment: pw.CrossAxisAlignment.start,
              children: [
                pw.Text(
                  'VetDental',
                  style: pw.TextStyle(
                    color: PdfColors.white,
                    fontWeight: pw.FontWeight.bold,
                    fontSize: 12,
                  ),
                ),
                pw.SizedBox(height: 8),
                pw.Text(
                  'AI Dental Assessment',
                  style: pw.TextStyle(
                    color: PdfColors.white,
                    fontSize: 24,
                    fontWeight: pw.FontWeight.bold,
                  ),
                ),
              ],
            ),
          ),
          pw.SizedBox(height: 16),
          pw.Text('Pet: ${recorded(pet['pet_name'])}'),
          pw.Text('Species: ${recorded(pet['species'])}'),
          pw.Text(
            'Assessment ID: ${recorded(job['assessment_job_id'])}',
          ),
          pw.Text('Assessment date: ${assessmentDate()}'),
          heading('Screening summary'),
          pw.Text(
            'Screening outcome: ${recorded(decision['status'])}',
          ),
          pw.SizedBox(height: 6),
          pw.Text(recorded(decision['reason'])),
          pw.SizedBox(height: 10),
          pw.Text(
            'Experimental severity reference: '
                '${recorded(severity['label'])}',
          ),
          pw.SizedBox(height: 6),
          pw.Text(recorded(severity['reason'])),
          heading('Model predictions'),
          if (rows.isEmpty)
            pw.Text('Prediction details are not available.')
          else
            pw.TableHelper.fromTextArray(
              headers: ['Condition', 'Screening state', 'Model score'],
              data: rows,
              headerDecoration: pw.BoxDecoration(color: blue),
              headerStyle: pw.TextStyle(
                color: PdfColors.white,
                fontWeight: pw.FontWeight.bold,
              ),
              cellStyle: const pw.TextStyle(fontSize: 9),
              cellPadding: const pw.EdgeInsets.all(8),
              oddRowDecoration: pw.BoxDecoration(color: paleBlue),
            ),
          pw.SizedBox(height: 10),
          pw.Text(
            'Model scores do not measure disease severity. '
                'Not assessed means the condition was not evaluated '
                'for this assessment.',
            style: const pw.TextStyle(fontSize: 9),
          ),
          heading('Recommended next step'),
          pw.Text(
            'If the findings concern you, book a dental examination. '
                'An uncertain result can also be discussed with your vet. '
                'A normal-looking photo does not rule out dental problems.',
          ),
          pw.SizedBox(height: 16),
          pw.Container(
            padding: const pw.EdgeInsets.all(12),
            color: paleBlue,
            child: pw.Text(
              'AI screening reference - not a veterinary diagnosis. '
                  'This document records the original AI output. '
                  'Veterinary findings are recorded separately.',
              style: const pw.TextStyle(fontSize: 10),
            ),
          ),
        ],
      ),
    );

    document.addPage(
      pw.Page(
        pageFormat: PdfPageFormat.a4,
        margin: const pw.EdgeInsets.all(36),
        build: (_) => pw.Column(
          crossAxisAlignment: pw.CrossAxisAlignment.start,
          children: [
            heading('Submitted photo'),
            pw.Expanded(
              child: pw.Center(
                child: pw.Image(
                  pw.MemoryImage(originalImage),
                  fit: pw.BoxFit.contain,
                ),
              ),
            ),
            pw.SizedBox(height: 16),
            pw.Text(
              'Assessment #${recorded(job['assessment_job_id'])}',
            ),
          ],
        ),
      ),
    );

    document.addPage(
      pw.Page(
        pageFormat: PdfPageFormat.a4,
        margin: const pw.EdgeInsets.all(36),
        build: (_) => pw.Column(
          crossAxisAlignment: pw.CrossAxisAlignment.start,
          children: [
            heading('Combined AI visualization'),
            pw.Expanded(
              child: pw.Center(
                child: pw.Image(
                  pw.MemoryImage(combinedImage),
                  fit: pw.BoxFit.contain,
                ),
              ),
            ),
            pw.SizedBox(height: 12),
            pw.Text(
              'Heatmap colours show relative model attention. '
                  'Segmentation outlines show predicted image regions. '
                  'Neither confirms disease boundaries or clinical severity.',
              style: const pw.TextStyle(fontSize: 9),
            ),
          ],
        ),
      ),
    );

    return document.save();
  }
}