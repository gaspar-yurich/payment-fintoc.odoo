{
    'name': 'Fintoc Payments',
    'version': '17.0.1.0.0',
    'summary': 'Fintoc payment provider for redirects, webhooks and refunds',
    'description': """
Fintoc payment provider integration for Odoo 17.

Features:
- Redirect checkout session flow.
- Webhook-based payment and refund status synchronization.
- Refund requests from Odoo.
- Collects/Direct collection mode support.
""",
    'category': 'Accounting/Payment',
    'author': 'Community',
    'license': 'LGPL-3',
    'depends': ['payment'],
    'external_dependencies': {
        'python': ['requests'],
    },
    'data': [
        'security/ir.model.access.csv',
        'views/payment_fintoc_templates.xml',
        'data/payment_method_data.xml',
        'data/payment_provider_data.xml',
        'views/payment_provider_views.xml',
        'views/payment_transaction_views.xml',
    ],
    'installable': True,
    'application': False,
}
