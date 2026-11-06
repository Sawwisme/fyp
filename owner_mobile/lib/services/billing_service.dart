import 'api_client.dart';

class BillingService {
  final ApiClient api;

  BillingService(this.api);

  Future<Map<String, dynamic>> getBills({
    String? status,
    int offset = 0,
    int limit = 10,
  }) async {
    final parameters = {
      'offset': '$offset',
      'limit': '$limit',
    };

    if (status != null) {
      parameters['bill_status'] = status;
    }

    final query = Uri(queryParameters: parameters).query;

    final data = await api.get('/owner-billing/bills?$query');

    if (data is! Map ||
        data['items'] is! List ||
        data['total'] is! int) {
      throw const ApiException('Invalid bill-list response.');
    }

    return Map<String, dynamic>.from(data);
  }

  Future<Map<String, dynamic>> getBill(int billId) async {
    final data = await api.get('/owner-billing/bills/$billId');

    if (data is! Map ||
        data['bill'] is! Map ||
        data['payments'] is! List) {
      throw const ApiException('Invalid bill response.');
    }

    return Map<String, dynamic>.from(data);
  }

  Future<Map<String, dynamic>> openCheckout(int billId) async {
    final data = await api.post(
      '/owner-billing/bills/$billId/checkout',
      {},
    );

    if (data is! Map) {
      throw const ApiException('Invalid payment response.');
    }

    return Map<String, dynamic>.from(data);
  }

  Future<void> cancelOnlineAttempt(int billId) async {
    final data = await api.post(
      '/owner-billing/bills/$billId/cancel-online',
      {},
    );

    if (data is! Map ||
        data['consultation_bill_id'] != billId ||
        data['payment_attempt_closed'] != true) {
      throw const ApiException(
        'Cannot confirm that the online payment attempt is closed.',
      );
    }
  }
}