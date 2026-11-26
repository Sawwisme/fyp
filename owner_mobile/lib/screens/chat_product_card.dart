import 'package:flutter/material.dart';

import '../services/api_client.dart';
import '../services/cart_service.dart';
import '../services/checkout_service.dart';
import 'cart.dart';
import 'checkout.dart';

class ChatProductCard extends StatefulWidget {
  final CartService service;
  final Map<String, dynamic> product;
  final bool enabled;
  final String language;

  const ChatProductCard({
    super.key,
    required this.service,
    required this.product,
    required this.enabled,
    this.language = 'en',
  });

  @override
  State<ChatProductCard> createState() => _ChatProductCardState();
}

class _ChatProductCardState extends State<ChatProductCard> {
  bool _busy = false;
  bool _uncertain = false;
  String? _message;
  int _quantity = 1;

  String _text(String en, String ms, String zh) {
    if (widget.language == 'ms') return ms;
    if (widget.language == 'zh') return zh;
    return en;
  }

  Future<void> _add({required bool checkout}) async {
    if (_busy || _uncertain || !widget.enabled) return;

    setState(() {
      _busy = true;
      _message = null;
    });

    var added = false;

    try {
      final clinicId = widget.product['clinic_id'] as int;
      final productId = widget.product['product_id'] as int;

// Read the current cart so existing quantities are preserved.
      final cart = await widget.service.getCart(clinicId);

      var existingQuantity = 0;

      for (final entry in cart['items'] as List) {
        final item = Map<String, dynamic>.from(entry as Map);

        if (item['product_id'] == productId) {
          existingQuantity = item['quantity'] as int;
          break;
        }
      }

      final requestedQuantity = existingQuantity + _quantity;

      if (requestedQuantity > 99) {
        throw const ApiException(
          'The cart can contain up to 99 units of one product.',
          statusCode: 422,
        );
      }

      await widget.service.setQuantity(
        clinicId: clinicId,
        productId: productId,
        expectedVersion: cart['version'] as int,
        quantity: requestedQuantity,
      );

      added = true;

      if (!mounted) return;

      setState(() {
        _message = '$_quantity '
            '${_quantity == 1 ? 'item' : 'items'} added to your clinic cart.';
      });

      if (checkout) {
        await Navigator.of(context).push<void>(
          MaterialPageRoute(
            builder: (_) => CheckoutScreen(
              service: CheckoutService(widget.service.api),
              clinicId: clinicId,
              selectedProductIds: [productId],
            ),
          ),
        );
      }
    } catch (error) {
      if (!mounted) return;

      final status = error is ApiException ? error.statusCode : null;

      final uncertain = !added &&
          (status == null ||
              status >= 500 ||
              (status >= 200 && status < 300));

      setState(() {
        _uncertain = uncertain;

        _message = uncertain
            ? 'The cart update could not be confirmed. Open your cart '
            'and check the quantity before making another change.'
            : added
            ? 'Item added. Open your cart to continue checkout.'
            : error.toString();
      });
    } finally {
      if (mounted) {
        setState(() => _busy = false);
      }
    }
  }

  Future<void> _openCart() async {
    if (_busy || !widget.enabled) return;

    setState(() => _busy = true);

    try {
      await Navigator.of(context).push<void>(
        MaterialPageRoute(
          builder: (_) => CartScreen(
            service: widget.service,
            clinicId: widget.product['clinic_id'] as int,
          ),
        ),
      );
    } finally {
      if (mounted) {
        setState(() => _busy = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final price = num.tryParse('${widget.product['price']}');
    final canAdd = widget.enabled && !_busy && !_uncertain;

    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(top: 12),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFFF4F6FC),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFFDCE2ED)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '${widget.product['product_name']}',
            style: const TextStyle(fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 4),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Icon(
                Icons.storefront_outlined,
                size: 16,
                color: Color(0xFF63718A),
              ),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  '${widget.product['clinic_name']}',
                  style: const TextStyle(
                    color: Color(0xFF63718A),
                  ),
                ),
              ),
            ],
          ),
          if ((widget.product['clinic_state'] ?? '')
              .toString()
              .trim()
              .isNotEmpty) ...[
            const SizedBox(height: 4),
            Text(
              '${widget.product['clinic_state']}',
              style: const TextStyle(
                fontSize: 12,
                color: Color(0xFF63718A),
              ),
            ),
          ],
          const SizedBox(height: 8),
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: [
              if (widget.product['shop_pickup_enabled'] == true)
                Chip(
                  avatar: const Icon(Icons.store_outlined, size: 16),
                  label: Text(
                    _text('Clinic pickup', 'Pengambilan di klinik', '诊所自取'),
                  ),
                  visualDensity: VisualDensity.compact,
                ),
              if (widget.product['shop_delivery_enabled'] == true)
                Chip(
                  avatar: const Icon(
                    Icons.local_shipping_outlined,
                    size: 16,
                  ),
                  label: Text(
                    _text(
                      'Delivery available',
                      'Penghantaran tersedia',
                      '提供配送',
                    ),
                  ),
                  visualDensity: VisualDensity.compact,
                ),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            _text(
              'Confirm current fulfilment options and any delivery '
                  'charges at checkout.',
              'Sahkan kaedah penerimaan dan caj penghantaran '
                  'semasa di checkout.',
              '请在结账时确认当前收货方式及配送费用。',
            ),
            style: const TextStyle(
              fontSize: 11,
              color: Color(0xFF63718A),
            ),
          ),
          const SizedBox(height: 10),
          Text(
            price == null
                ? _text(
              'Check price at checkout',
              'Semak harga di checkout',
              '在结账时查看价格',
            )
                : 'RM ${price.toStringAsFixed(2)}',
          ),
          const SizedBox(height: 10),
          if ((widget.product['recommendation_reason'] ?? '')
              .toString()
              .trim()
              .isNotEmpty) ...[
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: const Color(0xFFEAF0FF),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    _text(
                      'Why this matches',
                      'Sebab produk ini sepadan',
                      '推荐原因',
                    ),
                    style: const TextStyle(
                      color: Color(0xFF2549C7),
                      fontWeight: FontWeight.w700,
                      fontSize: 12,
                    ),
                  ),
                  const SizedBox(height: 5),
                  Text(
                    '${widget.product['recommendation_reason']}',
                    style: const TextStyle(fontSize: 12, height: 1.5),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 10),
          ],

          if ((widget.product['suitability_notes'] ?? '')
              .toString()
              .trim()
              .isNotEmpty) ...[
            Text(
              '${_text('Label notes', 'Nota label', '产品标签说明')}: '
                  '${widget.product['suitability_notes']}',
              style: const TextStyle(
                fontSize: 12,
                color: Color(0xFF53627A),
              ),
            ),
            const SizedBox(height: 10),
          ],

          DropdownButtonFormField<int>(
            initialValue: _quantity,
            decoration: InputDecoration(
              labelText: _text(
                'Quantity to add',
                'Kuantiti untuk ditambah',
                '添加数量',
              ),
              border: const OutlineInputBorder(),
              isDense: true,
            ),
            items: [
              for (var value = 1; value <= 10; value++)
                DropdownMenuItem(
                  value: value,
                  child: Text('$value'),
                ),
            ],
            onChanged: canAdd
                ? (value) {
              if (value == null) return;
              setState(() => _quantity = value);
            }
                : null,
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              OutlinedButton(
                onPressed: canAdd ? () => _add(checkout: false) : null,
                child: Text(_text('Add to cart', 'Tambah ke troli', '加入购物车')),
              ),
              FilledButton(
                onPressed: canAdd ? () => _add(checkout: true) : null,
                child: Text(
                  _busy
                      ? _text('Please wait…', 'Sila tunggu…', '请稍候…')
                      : _text('Buy now', 'Beli sekarang', '立即购买'),
                ),
              ),
              TextButton(
                onPressed: widget.enabled && !_busy ? _openCart : null,
                child: Text(_text('View cart', 'Lihat troli', '查看购物车')),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            _text(
              'Buy now opens checkout for this product only. '
                  'Any existing quantity of the same product is included. '
                  'Price and stock are checked again.',
              'Beli sekarang membuka checkout untuk produk ini sahaja. '
                  'Kuantiti produk sama yang sudah berada dalam troli turut '
                  'disertakan. Harga dan stok disemak semula.',
              '立即购买只为此产品打开结账页面。'
                  '购物车中该产品已有的数量也会计入。'
                  '价格和库存将再次检查。',
            ),
            style: const TextStyle(
              fontSize: 12,
              color: Color(0xFF53627A),
            ),
          ),
          if (_message != null) ...[
            const SizedBox(height: 8),
            Text(_message!),
          ],
        ],
      ),
    );
  }
}