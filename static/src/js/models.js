odoo.define('pos_cardano.models', function (require) {
var models = require('point_of_sale.models');
var PaymentAdyen = require('pos_cardano.payment');

models.register_payment_method('cardano', PaymentAdyen);
models.load_fields('pos.payment.method', ['cardano_terminal_identifier', 'cardano_test_mode', 'cardano_wallet_address']);
});
