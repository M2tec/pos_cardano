# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'POS Cardano',
    'version': '1.0',
    'category': 'Sales/Point Of Sale',
    'sequence': 6,
    'summary': 'Integrate your POS with the Cardano blockchain payment system',
    'description': '',
    'data': [
        'views/pos_config_views.xml',
        'views/pos_payment_method_views.xml',
        'views/point_of_sale_assets.xml',
    ],
    'depends': ['point_of_sale'],
    'qweb': ['static/src/xml/pos.xml'],
    'installable': True,
    'license': 'LGPL-3',
}
