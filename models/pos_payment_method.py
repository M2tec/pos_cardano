# coding: utf-8
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import json
import logging
from pprint import pprint
import random
import requests
import string

from cardano.wallet import Wallet
from cardano.wallet import WalletService
from cardano.backends.walletrest import WalletREST

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

    @api.model
    def get_latest_cardano_status(self, data):
        '''See the description of proxy_cardano_request as to why this is an
        @api.model function.
        '''
        _logger.info('---Cardano get_latest_cardano_status ----')
        print('cardano_status')
        pprint(data)
                
        # Poll the status of the terminal if there's no new
        # notification we received. This is done so we can quickly
        # notify the user if the terminal is no longer reachable due
        # to connectivity issues.

        #payment_method = self.sudo().browse(payment_method_id)
        #latest_response = payment_method.cardano_latest_response
        
        
        #latest_response = json.loads(latest_response) if latest_response else False
        #payment_method.cardano_latest_response = ''  # avoid handling old responses multiple times

        transaction_id = data["transaction_id"]
        wallet_id = data["wallet_id"]
        requested_amount = data["requested_amount"]        

        def check_payment_local_node(network_type, transaction_id, wallet_id, requested_amount):
            wallet_port = 8090

            print('Connecting to wallet')

            wal0 = Wallet(wallet_id, backend=WalletREST(port=wallet_port))
            wal0.sync_progress()
            
            wallet_balance = wal0.balance().total
            # print('wallet balance')
            # print(wal0.balance().total)
            
            tnxs = wal0.transactions()
            
            transact = []
            
            result = "not_received"
            
            for tnx in tnxs:
                tnx_dict = {'id': tnx.txid, 'fee': tnx.fee, 'input': tnx.amount_in, 'output': tnx.amount_out, 'metadata': tnx.metadata, 'status' : tnx.status}
                
                #print(dir(tnx))
                print('\n')
                print(repr(tnx_dict))
                print('\n')
                
                metadata = tnx.metadata
                #print(metadata.keys())
                
                tx_id = ''
                
                try:
                    tx_id = metadata[73]['title']
                    print('tx_id: ' + str(tx_id))
                    print('transaction_id: ' + transaction_id)
                    print(': ' + transaction_id)
                             
                    if tx_id == transaction_id and tnx.amount_in >= requested_amount:
                        print("-------------- Success -------------")
                        result = "success"   
                    elif tx_id == transaction_id and tnx.amount_in < requested_amount:
                        result = "Recieved amount too low => Requested: " + str(requested_amount) + "Recieved: " + str(tnx.amount_in)  
         
                except KeyError:
                    pass
                
                return result 
                
        def check_payment_koios(network_type, transaction_id, wallet_id, requested_amount):
                
            wallet_address = 'addr_test1qzn58ztr9t4eaxxzg4nxr7drzfe4gpl0rkx0rjjp70q3nzwm4uhvu74emhsyrtpqpqjt0hk2mflktqrvl3dn5hym6pes9nrq8r'     
            json_data = {"_addresses":[wallet_address]}

            base_url = "https://d.koios-api." + network_type + ".dandelion.link/rpc"

            url = base_url + "/address_txs"
            print(url)
            headers = {'Content-type': 'application/json'}                    
            r = requests.post(url, headers=headers, json=json_data)
            pprint((r.text))
            
            result = "not_received"
            
            json_response = json.loads(r.text)
            
            # Check metadata
            for j in json_response:
                print()
                print("-------Hash:" + j + "--------")

                json_data = {"_tx_hashes": [j]}

                url = base_url + "/tx_metadata"
                #print(url)
                
                headers = {'Content-type': 'application/json'}                    
                r = requests.post(url, headers=headers, json=json_data)
                #pprint((r.text))

                json_response = json.loads(r.text)
                metadata_title = json_response[0]['metadata']['73']['title']

                print()
                print(metadata_title)
                print()
                
                if metadata_title == transaction_id:                                   

                    print("-----confirm value-----")
                    url = base_url + "/tx_utxos"
                    headers = {'Content-type': 'application/json'}                    
                    r = requests.post(url, headers=headers, json=json_data)
                    
                    tx_utxos = json.loads(r.text)
                    
                    utxo_output = tx_utxos[0]["outputs"]

                    for u in utxo_output:
                        payment_addr = u["payment_addr"]["bech32"]
                        
                        if wallet_address == payment_addr:               
                            utxo_pay_amount = float(u["value"])/1000000
                    
                    print(utxo_pay_amount)

                    if utxo_pay_amount >= requested_amount:
                        result = "success"  
                
                #print()
                #pprint(type(json.loads(r.text)))
            
                #print()
                #print(json.dumps(tx_utxos, indent=4, sort_keys=True))
            
            return result     
            
        result = check_payment_koios('testnet', transaction_id, wallet_id, requested_amount)
        #result = check_payment_local_node('testnet', transaction_id, wallet_id, requested_amount)

        return { 'response': result }

    @api.model
    def request_payment(self, data):
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
        #pprint(data)

        # Generate a new wallet_address from the wallet_id
        transaction_id = data["transaction_id"]
        wallet_id = data["wallet_id"]
        requested_amount = data["requested_amount"]

        #wallet = Wallet(wallet_id, backend=WalletREST(port=8090))
        # wallet_address = str(wallet.first_unused_address())
        wallet_address = 'addr_test1qzn58ztr9t4eaxxzg4nxr7drzfe4gpl0rkx0rjjp70q3nzwm4uhvu74emhsyrtpqpqjt0hk2mflktqrvl3dn5hym6pes9nrq8r'
        # print(wallet_address)
    
        # Send payment request to the m2_kiosk_app
        url = "http://localhost:9090/payment-request"
        json_data={"transaction_id": transaction_id, 
                   "wallet_address": wallet_address, 
                   "requested_amount": requested_amount}
                                
        r = requests.post(url, json.dumps(json_data))
        
        return True


    @api.onchange('use_payment_terminal')
    def _onchange_use_payment_terminal(self):
        super(PosPaymentMethod, self)._onchange_use_payment_terminal()
        if self.use_payment_terminal != 'cardano':
            self.cardano_wallet_address = False
            self.cardano_terminal_identifier = False

