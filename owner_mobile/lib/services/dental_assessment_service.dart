import 'dart:typed_data';

import 'package:http/http.dart' as http;

import 'api_client.dart';

class DentalAssessmentService {
  final ApiClient api;

  DentalAssessmentService(this.api);

  Future<Map<String, dynamic>> uploadPhoto(
      int petId,
      Uint8List photo,
      ) async {
    if (photo.isEmpty || photo.lengthInBytes > 8 * 1024 * 1024) {
      throw const ApiException(
        'Choose a non-empty photo smaller than 8 MB.',
      );
    }

    final data = await api.postMultipart(
      '/dental-images/pets/$petId',
      fields: {},
      files: [
        http.MultipartFile.fromBytes(
          'file',
          photo,
          filename: 'dental-photo.jpg',
        ),
      ],
    );

    if (data is! Map<String, dynamic> ||
        data['dental_image_id'] is! int ||
        data['status'] != 'uploaded') {
      throw const ApiException(
        'The server did not confirm the photo upload.',
      );
    }

    return data;
  }

  Future<Map<String, dynamic>> startAssessment(int imageId) async {
    final data = await api.post(
      '/dental-assessments/images/$imageId',
      {},
    );

    if (data is! Map<String, dynamic> ||
        data['assessment_job_id'] is! int) {
      throw const ApiException(
        'The server did not confirm the assessment request.',
      );
    }

    return data;
  }

  Future<Map<String, dynamic>> getAssessment(int jobId) async {
    final data = await api.get(
      '/dental-assessments/$jobId',
    );

    if (data is! Map<String, dynamic> ||
        data['assessment_job_id'] != jobId) {
      throw const ApiException(
        'Invalid assessment status response.',
      );
    }

    return data;
  }

  Future<Uint8List> getResultImage(
      int jobId,
      String kind,
      ) {
    if (!{'heatmap', 'segmentation', 'summary'}.contains(kind)) {
      throw const ApiException('Invalid result image type.');
    }

    return api.getBytes(
      '/dental-assessments/$jobId/media/$kind',
    );
  }
}