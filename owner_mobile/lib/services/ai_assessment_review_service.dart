import 'api_client.dart';

class AIAssessmentReviewService {
  final ApiClient api;
  AIAssessmentReviewService(this.api);

  Map<String, dynamic> _record(dynamic data) {
    if (data is! Map<String, dynamic> ||
        data['review_id'] is! int ||
        data['analysis_id'] is! int ||
        !{'pending', 'reviewed', 'cancelled'}.contains(data['status'])) {
      throw const ApiException('Invalid assessment review response.');
    }
    return data;
  }

  Future<List<Map<String, dynamic>>> list({
    int offset = 0,
    int limit = 21,
  }) async {
    final query = Uri(
      queryParameters: {'offset': '$offset', 'limit': '$limit'},
    ).query;
    final data = await api.get('/ai-assessment-reviews?$query');
    if (data is! List)
      throw const ApiException('Invalid review list response.');
    return data.map(_record).toList();
  }

  Future<Map<String, dynamic>> get(int reviewId) async {
    final record = _record(await api.get('/ai-assessment-reviews/$reviewId'));
    if (record['review_id'] != reviewId) {
      throw const ApiException('The server returned a different review.');
    }
    return record;
  }

  Future<Map<String, dynamic>> request({
    required int analysisId,
    required int clinicId,
    String? ownerMessage,
  }) async {
    final record = _record(
      await api.post('/ai-assessment-reviews/assessments/$analysisId', {
        'clinic_id': clinicId,
        'owner_message': ownerMessage?.trim(),
      }),
    );
    if (record['analysis_id'] != analysisId ||
        record['clinic_id'] != clinicId) {
      throw const ApiException(
        'The server did not confirm the selected assessment and clinic.',
      );
    }
    return record;
  }
}
