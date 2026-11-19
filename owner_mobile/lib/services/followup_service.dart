import 'dart:typed_data';

import 'package:http/http.dart' as http;

import 'api_client.dart';

class FollowupService {
  final ApiClient api;

  FollowupService(this.api);

  Future<List<Map<String, dynamic>>> getSubmissions(
      int followupId, {
        int offset = 0,
        int limit = 21,
      }) async {
    final data = await api.get(
      '/owner-followups/$followupId/submissions'
          '?offset=$offset&limit=$limit',
    );

    if (data is! List) {
      throw const ApiException('Invalid submission history response.');
    }

    return data.map((item) {
      if (item is! Map<String, dynamic>) {
        throw const ApiException('Invalid submission record.');
      }

      return item;
    }).toList();
  }

  Future<Map<String, dynamic>> submitUpdate(
      int followupId, {
        required String comment,
        required List<Uint8List> photos,
      }) async {
    if (photos.length > 4) {
      throw const ApiException('Select up to four photos.');
    }

    if (comment.trim().length > 5000) {
      throw const ApiException('The comment is too long.');
    }

    if (photos.isEmpty && comment.trim().isEmpty) {
      throw const ApiException('Add a photo or a progress comment.');
    }

    for (final photo in photos) {
      if (photo.isEmpty || photo.lengthInBytes > 8 * 1024 * 1024) {
        throw const ApiException(
          'Each photo must be non-empty and 8 MB or smaller.',
        );
      }
    }

    final data = await api.postMultipart(
      '/owner-followups/$followupId/submissions',
      timeout: const Duration(seconds: 150),
      fields: {'owner_comment': comment.trim()},
      files: [
        for (var index = 0; index < photos.length; index++)
          http.MultipartFile.fromBytes(
            'files',
            photos[index],
            filename: 'photo-${index + 1}.jpg',
          ),
      ],
    );

    if (data is! Map<String, dynamic>) {
      throw const ApiException(
        'Unexpected upload response. Check submission history.',
      );
    }

    return data;
  }

  Future<Uint8List> getPhoto(int imageId) {
    return api.getBytes('/followup-media/$imageId');
  }

  Future<Map<String, dynamic>> getSubmissionState(
      int followupId,
      ) async {
    final data = await api.get(
      '/owner-followups/$followupId/submission-state',
    );

    if (data is! Map<String, dynamic> ||
        data['can_submit'] is! bool ||
        data['submission_state'] is! String) {
      throw const ApiException('Invalid follow-up status response.');
    }

    return data;
  }

  Future<List<Map<String, dynamic>>> getFollowups({
    String? status,
    int offset = 0,
    int limit = 11,
  }) async {
    final query = Uri(
      queryParameters: {
        if (status != null) 'task_status': status,
        'offset': '$offset',
        'limit': '$limit',
      },
    ).query;

    final data = await api.get('/owner-followups?$query');

    if (data is! List) {
      throw const ApiException('Invalid follow-up list response.');
    }

    return data.map((item) {
      if (item is! Map<String, dynamic>) {
        throw const ApiException('Invalid follow-up record.');
      }
      return item;
    }).toList();
  }

  Future<Map<String, dynamic>> getBookingContext(int followupId) async {
    final data = await api.get(
      '/owner-followups/$followupId/booking-context',
    );

    if (data is! Map<String, dynamic>) {
      throw const ApiException('Invalid follow-up booking response.');
    }

    return data;
  }
}