# coding: utf-8
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class PosConfig(models.Model):
    _inherit = 'pos.config'

    cardano_ask_customer_for_tip = fields.Boolean('Ask Customers For Tip', help='Prompt the customer to tip.')

    @api.constrains('cardano_ask_customer_for_tip', 'iface_tipproduct', 'tip_product_id')
    def _check_cardano_ask_customer_for_tip(self):
        for config in self:
            if config.cardano_ask_customer_for_tip and (not config.tip_product_id or not config.iface_tipproduct):
                raise ValidationError(_("Please configure a tip product for POS %s to support tipping with cardano.") % config.name)

    @api.onchange('cardano_ask_customer_for_tip')
    def _onchange_cardano_ask_customer_for_tip(self):
        for config in self:
            if config.cardano_ask_customer_for_tip:
                config.iface_tipproduct = True
