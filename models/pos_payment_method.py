# coding: utf-8
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import json
import logging
import pprint
import random
import requests
import string

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gio, GLib

class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'

    def _get_payment_terminal_selection(self):
        return super(PosPaymentMethod, self)._get_payment_terminal_selection() + [('cardano', 'Cardano')]

    cardano_wallet_address = fields.Char(string="Cardano Wallet Id", help='Enter your wallet id here. This is where customers deposit their ADA', copy=False)
    cardano_terminal_identifier = fields.Char(help='[Terminal model]-[Serial number], for example: P400Plus-123456789', copy=False)
    cardano_test_mode = fields.Boolean(help='Run transactions in the test environment.')
    cardano_latest_response = fields.Char(help='Technical field used to buffer the latest asynchronous notification from Cardano.', copy=False, groups='base.group_erp_manager')
    cardano_latest_diagnosis = fields.Char(help='Technical field used to determine if the terminal is still connected.', copy=False, groups='base.group_erp_manager')

    @api.constrains('cardano_terminal_identifier')
    def _check_cardano_terminal_identifier(self):
        for payment_method in self:
            if not payment_method.cardano_terminal_identifier:
                continue
            existing_payment_method = self.search([('id', '!=', payment_method.id),
                                                   ('cardano_terminal_identifier', '=', payment_method.cardano_terminal_identifier)],
                                                  limit=1)
            if existing_payment_method:
                raise ValidationError(_('Terminal %s is already used on payment method %s.')
                                      % (payment_method.cardano_terminal_identifier, existing_payment_method.display_name))

    def _is_write_forbidden(self, fields):
        whitelisted_fields = set(('cardano_latest_response', 'cardano_latest_diagnosis'))
        return super(PosPaymentMethod, self)._is_write_forbidden(fields - whitelisted_fields)

    def _cardano_diagnosis_request_data(self, pos_config_name, terminal_identifier):
        service_id = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
        return {
            "SaleToPOIRequest": {
                "MessageHeader": {
                    "ProtocolVersion": "3.0",
                    "MessageClass": "Service",
                    "MessageCategory": "Diagnosis",
                    "MessageType": "Request",
                    "ServiceID": service_id,
                    "SaleID": pos_config_name,
                    "POIID": terminal_identifier,
                },
                "DiagnosisRequest": {
                    "HostDiagnosisFlag": False
                }
            }
        }

    @api.model
    def get_latest_cardano_status(self, payment_method_id, pos_config_name, terminal_identifier, test_mode, api_key):
        '''See the description of proxy_cardano_request as to why this is an
        @api.model function.
        '''

        # Poll the status of the terminal if there's no new
        # notification we received. This is done so we can quickly
        # notify the user if the terminal is no longer reachable due
        # to connectivity issues.
        self.proxy_cardano_request(self._cardano_diagnosis_request_data(pos_config_name, terminal_identifier),
                                 test_mode,
                                 api_key)

        payment_method = self.sudo().browse(payment_method_id)
        latest_response = payment_method.cardano_latest_response
        
        
        latest_response = json.loads(latest_response) if latest_response else False
        payment_method.cardano_latest_response = ''  # avoid handling old responses multiple times

        return {
            'latest_response': latest_response,
            'last_received_diagnosis_id': payment_method.cardano_latest_diagnosis,
        }

    @api.model
    def proxy_cardano_request(self, data, test_mode, api_key):
        '''Necessary because Cardano's endpoints don't have CORS enabled. This is an
        @api.model function to avoid concurrent update errors. Cardano's
        async endpoint can still take well over a second to complete a
        request. By using @api.model and passing in all data we need from
        the POS we avoid locking the pos_payment_method table. This way we
        avoid concurrent update errors when Cardano calls us back on
        /pos_cardano/notification which will need to write on
        pos.payment.method.
        '''
        _logger.info('---Cardano request ----')
         
        _logger.info('request to cardano\n%s', pprint.pformat(data))
        
        message_category = data['SaleToPOIRequest']['MessageHeader']['MessageCategory']
        #print("message_category = " + message_category)

        def poll_allive(msg):

            var = GLib.Variant("(s)", (msg,))  # Parameters should be variant.
            ret_var = proxy.call_sync(
                "PollAlive",  # Method name
                var,  # Parameters for method
                Gio.DBusCallFlags.NO_AUTO_START,  # Flags for call APIs
                500,  # How long to wait for reply? (in milliseconds)
                None,  # Cancellable, to cancel the call if you changed mind in middle)
            )
            service_id = ret_var.unpack()[0]
            #print(service_id)
            return service_id

        def request_payment(transaction_id, wallet_address, pay_amount, service_id):
            #print(pay_amount)
            var = GLib.Variant("(ssss)", (transaction_id, wallet_address, str(pay_amount), service_id,))     
            ret_var = proxy.call_sync(
                "SetPayment", var, Gio.DBusCallFlags.NO_AUTO_START, 500, None
            )
            greeting = ret_var.unpack()[0]
            #print(greeting)
            
        # Start dbus message bus       
        bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)  
        proxy = Gio.DBusProxy.new_sync(
            bus,
            Gio.DBusProxyFlags.NONE,
            None,
            "org.m2tec.paypad",
            "/org/m2tec/paypad",
            "org.m2tec.paypad",
            None,
        )
        
        diagnosis_data = ""
        
        if message_category == "Payment":
            _logger.info('---Payment message----')

            wallet_address = api_key
            pay_amount = data['SaleToPOIRequest']['PaymentRequest']['PaymentTransaction']['AmountsReq']['RequestedAmount']
            transaction_id = data['SaleToPOIRequest']['PaymentRequest']['SaleData']['SaleTransactionID']['TransactionID']
            service_id = data['SaleToPOIRequest']['MessageHeader']['ServiceID']

            request_payment(transaction_id, wallet_address, pay_amount, service_id)
                
        elif message_category == "Diagnosis":
            _logger.info('---Diagnosis message----')

            service_id = poll_allive("hi")
 
 
        #_logger.info('json_data\n%s', pprint.pformat(diagnosis_data))        

        return True


    @api.onchange('use_payment_terminal')
    def _onchange_use_payment_terminal(self):
        super(PosPaymentMethod, self)._onchange_use_payment_terminal()
        if self.use_payment_terminal != 'cardano':
            self.cardano_wallet_address = False
            self.cardano_terminal_identifier = False
